// Initialize chat history array
let chatHistory = [];
let mediaRecorder;
let audioChunks = [];
let audioContext;
let recognition;
let isRecording = false;
let voicesLoaded = false; // Flag to check if voices are preloaded 
const MIN_DECIBELS = -45; // Adjust this threshold based on your needs
const phraseTimeout = 3000; // Adjust this timeout based on your needs

// Track used actions from Task Breakdown to highlight in Available Actions
let usedActions = new Set();

// Caches to prevent unnecessary re-renders (anti-blink). Each cache stores the
// last rendered payload string; the corresponding DOM is only touched when the
// payload truly changes.
let lastPredefinedLib = null;
let lastCustomLib = null;
let lastComponentsPayload = null;
let lastNaturalLanguagePlans = null;
let lastLogicalRelations = null;
let lastExplanation = null;
let lastCurrentCode = null;
let lastCurrentInstruction = null;
let lastHighLevelTask = null;

// Preload voices to reduce delays in speech synthesis
function preloadVoices() {
  if ('speechSynthesis' in window) {
    let voices = window.speechSynthesis.getVoices();
    if (voices.length > 0) {
      voicesLoaded = true;
      console.log('Voices preloaded:', voices);
    } else {
      window.speechSynthesis.onvoiceschanged = () => {
        voices = window.speechSynthesis.getVoices();
        voicesLoaded = true;
        console.log('Voices loaded after change:', voices);
      };
    }
  }
}

// Call preloadVoices on page load to ensure voices are ready
window.onload = preloadVoices;

// Initialize Web Speech API for Speech-to-Text (STT)
if ('webkitSpeechRecognition' in window) {
  recognition = new webkitSpeechRecognition();
  recognition.continuous = false; // Stop after one phrase
  recognition.interimResults = true; // Show interim results
  recognition.lang = 'en-US'; // Set language to English

  recognition.onstart = function () {
    console.log('Speech recognition started.');
  };

  recognition.onresult = function (event) {
    let interimTranscript = '';
    let finalTranscript = '';

    for (let i = event.resultIndex; i < event.results.length; i++) {
      const transcript = event.results[i][0].transcript;
      if (event.results[i].isFinal) {
        finalTranscript += transcript;
      } else {
        interimTranscript += transcript;
      }
    }

    // Display interim and final results in real time
    document.getElementById('userInput').value = interimTranscript || finalTranscript;

    // If the final transcription is available, process it
    // if (finalTranscript) {
    //   processTranscription(finalTranscript.trim());
    // }
  };

  recognition.onerror = function (event) {
    console.error('Speech recognition error:', event);
  };

  recognition.onend = function () {
    console.log('Speech recognition ended.');
  };
}

// Add click event to record button
document.getElementById('recordButton').addEventListener('click', startRecording);

// Initialize MediaRecorder and recording context (if needed for saving the audio)
function initializeRecording(stream) {
  if (!audioContext) {
    audioContext = new AudioContext();
  }
  const audioStreamSource = audioContext.createMediaStreamSource(stream);
  const analyser = audioContext.createAnalyser();
  analyser.minDecibels = MIN_DECIBELS;
  audioStreamSource.connect(analyser);

  mediaRecorder = new MediaRecorder(stream);
  mediaRecorder.ondataavailable = event => {
    if (event.data.size > 0) audioChunks.push(event.data);
  };

  mediaRecorder.onstop = () => {
    console.log('Recording stopped.');
    // Optionally, process the audio data here if needed
  };

  return analyser;
}

async function startRecording() {
  if (isRecording) {
    stopRecording();
    return;
  }

  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    const analyser = initializeRecording(stream); // Initializes MediaRecorder and other components

    recognition.start(); // Start speech recognition (STT)
    detectSound(analyser);
    mediaRecorder.start();

    isRecording = true;
    updateRecordButtonState(isRecording);
  } catch (error) {
    console.error('Error accessing media devices:', error);
  }
}

// Stop recording for both STT and media
function stopRecording() {
  if (mediaRecorder && mediaRecorder.state === 'recording') {
    mediaRecorder.stop(); // Stop audio recording
  }
  if (recognition) {
    recognition.stop(); // Stop speech recognition
  }
  isRecording = false;
  updateRecordButtonState(isRecording);
}

// Automatically stop recording based on silence detection
function detectSound(analyser) {
  let lastSoundTimestamp = null;
  const bufferLength = analyser.frequencyBinCount;
  const frequencyData = new Uint8Array(bufferLength);

  const checkSound = () => {
    analyser.getByteFrequencyData(frequencyData);
    const now = Date.now();
    const isSoundDetected = frequencyData.some(value => value > 0);

    if (isSoundDetected) {
      lastSoundTimestamp = now;
    } else if (lastSoundTimestamp && now - lastSoundTimestamp > phraseTimeout) {
      stopRecording();
      return;
    }

    requestAnimationFrame(checkSound); // Check sound levels recursively
  };

  checkSound(); // Start checking sound levels
}

// Process the final transcription from Web Speech API
function processTranscription(transcription) {
  if (checkInputEmpty(transcription, true)) {
    return;
  }

  // Send the transcription to the server for further processing if needed
  submitTextInput(transcription);
}

// Function to submit the text input (transcribed or typed) to the server
async function submitTextInput(transcription) {
  try {
    const response = await fetch('/process_text_input', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
      },
      body: 'text_input=' + encodeURIComponent(transcription),
    });

    const result = await response.text();
    displayResponse(transcription, result);

    // Convert the response to speech using TTS
    speakText(result);

    document.getElementById('userInput').value = '';
  } catch (error) {
    console.error('Error submitting text input:', error);
  }
}

// Handle manual form submission
async function submitForm(event) {
  event.preventDefault();

  const data = document.getElementById('userInput').value;

  if (checkInputEmpty(data, false)) {
    return;
  }

  submitTextInput(data);
}

// Display user input and server response in chat history
function displayResponse(userInput, responseText) {
  const chatHistoryDiv = document.getElementById('chatHistory');

  const userMessageDiv = document.createElement('div');
  userMessageDiv.classList.add('message', 'user-message');
  userMessageDiv.style.whiteSpace = 'pre-wrap';
  userMessageDiv.style.textAlign = 'right';
  userMessageDiv.textContent = userInput;
  chatHistoryDiv.appendChild(userMessageDiv);

  const responseMessageDiv = document.createElement('div');
  responseMessageDiv.classList.add('message', 'response-message');
  responseMessageDiv.style.whiteSpace = 'pre-wrap';
  responseMessageDiv.style.textAlign = 'left';
  responseMessageDiv.textContent = responseText;
  chatHistoryDiv.appendChild(responseMessageDiv);

  chatHistoryDiv.scrollTop = chatHistoryDiv.scrollHeight;
}

// Check if user input is empty and display a response accordingly
function checkInputEmpty(userInput, speech) {
  if (userInput === '') {
    const message = speech ?
      'Sorry, I could not catch that. Please try again.' :
      'Please type something.';
    
    displayResponse(userInput, message);
    speakText(message);
    return true;
  }
  return false;
}

// Update record button's appearance based on recording state
function updateRecordButtonState(isRecording) {
  const recordButton = document.getElementById('recordButton');
  if (isRecording) {
    recordButton.classList.add('recording');
  } else {
    recordButton.classList.remove('recording');
  }
}

// Optimized SpeakText function for TTS
function speakText(text) {
  if ('speechSynthesis' in window) {
    if (!voicesLoaded) {
      console.warn('Voices are not yet loaded. Delaying speech synthesis.');
      return;
    }

    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = 'en-US'; // Set language
    utterance.pitch = 1; // Set pitch (1 is default)
    utterance.rate = 1.15; // Increase rate slightly for natural speech
    utterance.volume = 1; // Max volume

    // Optionally add event listeners for feedback
    utterance.onstart = () => {
      console.log('Speech synthesis started.');
    };

    utterance.onend = () => {
      console.log('Speech synthesis ended.');
    };

    utterance.onerror = (event) => {
      console.error('Speech synthesis error:', event);
    };

    // Speak immediately (since voices are already preloaded)
    window.speechSynthesis.speak(utterance);
  } else {
    console.error('Speech synthesis is not supported in this browser.');
  }
}

// Add click event to greet button
document.getElementById('greetButton').addEventListener('click', greet);

function greet(event) {
  // Prevent the default button click behavior
  event.preventDefault();

  // Send randomly selected greeting to the server
  const greetings = ['hi Spark', 'hello Spark', 'hey Spark', 'hi Spark bot', 'hello Spark bot', 'hey Spark bot', 'hi Spark robot', 'hello Spark robot', 'hey Spark robot', 'hi Sparky', 'hello Sparky', 'hey Sparky', 'hi Sparky bot', 'hello Sparky bot', 'hey Sparky bot', 'hi Sparky robot', 'hello Sparky robot', 'hey Sparky robot'];
  const randomGreeting = greetings[Math.floor(Math.random() * greetings.length)];

  submitTextInput(randomGreeting);
}

// @app.route('/get_current_instruction', methods=['GET'])
// def get_current_instruction():
//     global new_instruction_user_input
//     return jsonify({'instruction': new_instruction_user_input})
function updateCurrentInstruction() {
  fetch('/get_current_instruction')
      .then(response => response.json())
      .then(data => {
          const text = (data.instruction || '').split('</s>').join('');
          if (text === lastCurrentInstruction) return;
          lastCurrentInstruction = text;
          document.getElementById('currentInstruction').textContent = text;
      })
      .catch(error => console.error('Error fetching current instruction:', error));
}

// @app.route('/get_high_level_task', methods=['GET'])
// def get_high_level_task():
//     global high_level_task
//     return jsonify({'high_level_task': high_level_task})
function updateHighLevelTask() {
  fetch('/get_high_level_task')
      .then(response => response.json())
      .then(data => {
          const text = data.high_level_task || '';
          if (text === lastHighLevelTask) return;
          lastHighLevelTask = text;
          document.getElementById('highLevelTask').textContent = text;
      })
      .catch(error => console.error('Error fetching high-level task:', error));
}

// @app.route('/get_natural_language_plans', methods=['GET'])
// def get_natural_language_plans():
//     global natural_language_plans
//     return jsonify({'natural_language_plans': natural_language_plans})
function updateNaturalLanguagePlans() {
  fetch('/get_natural_language_plans')
      .then(response => response.json())
      .then(data => {
          const raw = data.natural_language_plans || '';
          if (raw === lastNaturalLanguagePlans) return;
          lastNaturalLanguagePlans = raw;
          document.getElementById('naturalLanguagePlans').innerHTML = raw
              .split('\n')
              .filter(plan => plan.trim())
              .map(plan => plan.replace(/^\s*(?:\d+[\).\]]|[-*•])\s+/, '').trim())
              .filter(plan => plan)
              .map(plan => `<li>${escapeHtml(plan)}</li>`)
              .join('');
      })
      .catch(error => console.error('Error fetching natural language plans:', error));
}

function escapeHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function highlightKeywords(text) {
  return escapeHtml(text)
    .replace(/\b(IF|ELSE|WHILE|REPEAT|END|TIMES)\b/g, '<code class="kw-control">$1</code>')
    .replace(/\b(FOUND_\w+|NEAR|FAR)\b/g, '<code class="kw-condition">$1</code>')
    .replace(/\b(FIND|MOVE_FORWARD|MOVE_LEFT|MOVE_RIGHT|TURN_LEFT|TURN_RIGHT|STAND_UP|STAND_DOWN|LIFT|SPIN_JUMP|FIRST_DANCE|SECOND_DANCE|TILT_LEFT_SHOULDER|TILT_RIGHT_SHOULDER|TILT_HEAD_UP|TILT_HEAD_DOWN|TILT_HEAD_LEFT|TILT_HEAD_RIGHT)\b/g, '<code class="kw-action">$1</code>');
}

// @app.route('/get_logical_relations', methods=['GET'])
// def get_logical_relations():
//     global logical_relations
//     return jsonify({'logical_relations': logical_relations})
function updateLogicalRelations() {
  fetch('/get_logical_relations')
      .then(response => response.json())
      .then(data => {
          const raw = data.logical_relations || '';
          if (raw === lastLogicalRelations) return;
          lastLogicalRelations = raw;
          const relations = raw.split('\n').filter(r => r.trim());
          document.getElementById('logicalRelations').innerHTML = relations
              .map(relation => `<li>${highlightKeywords(relation)}</li>`)
              .join('');
      })
      .catch(error => console.error('Error fetching logical relations:', error));
}

// @app.route('/get_components_for_pseudo_code', methods=['GET'])
// def get_components_for_pseudo_code():
//     global components_for_pseudo_code
//     return jsonify({'components_for_pseudo_code': components_for_pseudo_code})

// Action keywords for matching; refreshed from /get_current_libraries so the
// highlight and syntax coloring follow the active robot's vocabulary.
let allActionKeywords = [
  'STAND_DOWN', 'STAND_UP',
  'TILT_LEFT_SHOULDER', 'TILT_RIGHT_SHOULDER', 'TILT_HEAD_UP', 'TILT_HEAD_DOWN', 'TILT_HEAD_LEFT', 'TILT_HEAD_RIGHT',
  'MOVE_FORWARD', 'MOVE_LEFT', 'MOVE_RIGHT', 'TURN_LEFT', 'TURN_RIGHT',
  'SPIN_JUMP', 'LIFT', 'FIRST_DANCE', 'SECOND_DANCE',
  'FIND'
];

function updateComponentsForPseudoCode() {
  fetch('/get_components_for_pseudo_code')
      .then(response => response.json())
      .then(data => {
          const raw = data.components_for_pseudo_code || '';
          // Skip the entire DOM/state update when the payload is identical to
          // the last one. This single guard is what keeps highlights stable.
          if (raw === lastComponentsPayload) return;
          lastComponentsPayload = raw;

          const components = raw.split('\n').filter(c => c.trim());
          const actions = [];
          const controls = [];
          const conditions = [];

          const controlKeywords = ['IF', 'ELSE', 'WHILE', 'REPEAT', 'END', 'TIMES'];
          const conditionKeywords = ['FOUND', 'NEAR', 'FAR', 'DETECTED', 'TRUE', 'FALSE'];

          components.forEach(component => {
            const upperComp = component.toUpperCase();
            if (controlKeywords.some(kw => upperComp.includes(kw))) {
              controls.push(component);
            } else if (conditionKeywords.some(kw => upperComp.includes(kw))) {
              conditions.push(component);
            } else {
              actions.push(component);
            }
          });

          // Extract canonical action keywords from action components
          // (components may be like "FIND CHAIR" or "MOVE_FORWARD").
          const extractedActions = new Set();
          actions.forEach(action => {
            const upperAction = action.toUpperCase();
            allActionKeywords.forEach(keyword => {
              if (upperAction.includes(keyword)) {
                extractedActions.add(keyword);
              }
            });
          });

          const usedActionsChanged = !setsEqual(usedActions, extractedActions);
          usedActions = extractedActions;
          if (usedActionsChanged) {
            updateActionButtonHighlights();
          }

          renderComponentList('actionComponents', actions, 'action');
          renderComponentList('controlComponents', controls, 'control');
          renderComponentList('conditionComponents', conditions, 'condition');
      })
      .catch(error => console.error('Error fetching components for pseudo code:', error));
}

function renderComponentList(elementId, items, kind) {
  const el = document.getElementById(elementId);
  if (!el) return;
  if (items.length === 0) {
    el.innerHTML = '<div class="component-item empty">None</div>';
    return;
  }
  el.innerHTML = items
    .map(item => `<div class="component-item kind-${kind}">${escapeHtml(item)}</div>`)
    .join('');
}

// Helper function to compare two sets for equality
function setsEqual(setA, setB) {
  if (setA.size !== setB.size) return false;
  for (const item of setA) {
    if (!setB.has(item)) return false;
  }
  return true;
}

// Toggle the .active class on every action button based on the current
// `usedActions` set. The checkbox element is always in the DOM so we never
// add/remove nodes here — only a class flip — which prevents the highlight
// from flickering between polling cycles.
function updateActionButtonHighlights() {
  document.querySelectorAll('.action-btn').forEach(btn => {
    const actionName = btn.getAttribute('data-action');
    const shouldBeActive = !!(actionName && usedActions.has(actionName.toUpperCase()));
    if (btn.classList.contains('active') !== shouldBeActive) {
      btn.classList.toggle('active', shouldBeActive);
    }
  });
}

// @app.route('/get_explanation', methods=['GET'])
// def get_explanation():
//     global explanation
//     return jsonify({'explanation': explanation})
function updateExplanation() {
  fetch('/get_explanation')
      .then(response => response.json())
      .then(data => {
          const raw = data.explanation || '';
          if (raw === lastExplanation) return;
          lastExplanation = raw;
          const explanations = raw.split('\n').filter(e => e.trim());
          document.getElementById('explanation').innerHTML = explanations
              .map(item => `<li>${highlightKeywords(item)}</li>`)
              .join('');
      })
      .catch(error => console.error('Error fetching explanation:', error));
}

// @app.route('/get_current_libraries', methods=['GET'])
// def get_current_libraries():
//     global function_library
//     global new_function_library
//     return jsonify({'basic_function_library': function_library, 'new_function_library': list(new_function_library.keys())})

// Action icons mapping for visual enhancement
const actionIcons = {
  'MOVE_FORWARD': '→',
  'TURN_LEFT': '↰',
  'TURN_RIGHT': '↱',
  'STAND_UP': '🧍',
  'STAND_DOWN': '🧎',
  'LIFT': '🦿',
  'SPIN_JUMP': '🔄',
  'FIND': '🔍',
  'TILT_LEFT_SHOULDER': '↙',
  'TILT_RIGHT_SHOULDER': '↘',
  'TILT_HEAD_UP': '⬆',
  'TILT_HEAD_DOWN': '⬇',
  'TILT_HEAD_LEFT': '⬅',
  'TILT_HEAD_RIGHT': '⮕',
  'MOVE_LEFT': '⬅',
  'MOVE_RIGHT': '⮕',
  'FIRST_DANCE': '💃',
  'SECOND_DANCE': '🕺'
};

function buildActionButton(func, opts = {}) {
  const icon = opts.icon || actionIcons[func] || '⚡';
  const extraClass = opts.extraClass || '';
  // Checkbox markup is always present; highlighting is done purely via the
  // `.active` class on the parent button so polling never adds/removes nodes.
  return `<button class="action-btn ${extraClass}" data-action="${func}" type="button">
    <span class="icon" aria-hidden="true">${icon}</span>
    <span class="action-label">${escapeHtml(func)}</span>
    <span class="checkbox" aria-hidden="true"><span class="check">✓</span></span>
  </button>`;
}

function updateSupportedLibraries() {
  fetch('/get_current_libraries')
      .then(response => response.json())
      .then(data => {
          const predefinedEl = document.getElementById('predefinedLibraries');
          const customEl = document.getElementById('userDefinedLibraries');

          // Predefined buttons rarely change. Render only when the set of names
          // actually changes, then never touch the markup again.
          const predefinedKey = JSON.stringify(data.basic_function_library || []);
          if (predefinedKey !== lastPredefinedLib) {
            lastPredefinedLib = predefinedKey;
            predefinedEl.innerHTML = (data.basic_function_library || [])
              .map(func => buildActionButton(func))
              .join('');
          }

          const customList = data.new_function_library || [];
          allActionKeywords = (data.basic_function_library || []).concat(customList);
          const customKey = JSON.stringify(customList);
          if (customKey !== lastCustomLib) {
            lastCustomLib = customKey;
            if (customList.length > 0) {
              customEl.innerHTML = customList
                .map(func => buildActionButton(func, { extraClass: 'custom', icon: '⭐' }))
                .join('');
            } else {
              customEl.innerHTML = '<span class="empty-state">No custom actions defined yet</span>';
            }
          }

          // Always reconcile highlights against the latest `usedActions` —
          // pure class toggle, no DOM mutation, so this is flicker-free.
          updateActionButtonHighlights();
      })
      .catch(error => console.error('Error fetching current libraries:', error));
}

// function_library = ['STAND_DOWN', 'STAND_UP',
//   'TILT_LEFT_SHOULDER', 'TILT_RIGHT_SHOULDER', 'TILT_HEAD_UP', 'TILT_HEAD_DOWN', 'TILT_HEAD_LEFT', 'TILT_HEAD_RIGHT', 
//   'MOVE_FORWARD', 'MOVE_LEFT', 'MOVE_RIGHT', 'TURN_LEFT', 'TURN_RIGHT',
//   'SPIN_JUMP', 'LIFT', 'FIRST_DANCE', 'SECOND_DANCE',
//   'FIND']

function applySyntaxHighlighting(code) {
  // Define custom syntax highlighting rules
  const rules = [
      { pattern: /\b(IF|ELSE|WHILE|REPEAT|END|TIMES)\b/g, class: 'keyword' },
      { pattern: new RegExp('\\b(' + allActionKeywords.join('|') + ')\\b', 'g'), class: 'function' },
      { pattern: /\b\d+\b/g, class: 'number' },
      { pattern: /#.*/g, class: 'comment' }
  ];

  // Apply highlighting
  let highlightedCode = code;
  rules.forEach(rule => {
      highlightedCode = highlightedCode.replace(rule.pattern, match => `<span class="${rule.class}">${match}</span>`);
  });

  return highlightedCode;
}

function updateCurrentCode() {
  fetch('/get_current_code')
      .then(response => response.json())
      .then(data => {
          const raw = data.code || '';
          if (raw === lastCurrentCode) return;
          lastCurrentCode = raw;
          const highlightedCode = applySyntaxHighlighting(raw);
          document.getElementById('currentCode').innerHTML = highlightedCode.split('\n')
              .map((line, index) => `<code data-line-number="${index + 1}">${line || '&nbsp;'}</code>`)
              .join('');
      })
      .catch(error => console.error('Error fetching current code:', error));
}

// Initialize the page
document.addEventListener('DOMContentLoaded', (event) => {
  updateCurrentCode();
  updateSupportedLibraries();
  updateCurrentInstruction();
  updateHighLevelTask();
  updateNaturalLanguagePlans();
  updateLogicalRelations();
  updateComponentsForPseudoCode();
  updateExplanation();
});


// Call this function periodically or after each chat interaction
setInterval(updateCurrentCode, 5000); // Update every 5 seconds
setInterval(updateSupportedLibraries, 5000); // Update every 5 seconds
setInterval(updateCurrentInstruction, 5000); // Update every 5 seconds
setInterval(updateHighLevelTask, 5000); // Update every 5 seconds
setInterval(updateNaturalLanguagePlans, 5000); // Update every 5 seconds
setInterval(updateLogicalRelations, 5000); // Update every 5 seconds
setInterval(updateComponentsForPseudoCode, 5000); // Update every 5 seconds
setInterval(updateExplanation, 5000); // Update every 5 seconds