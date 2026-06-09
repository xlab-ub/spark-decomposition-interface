import cv2
# print(cv2.getBuildInformation())
import numpy as np

class camera:
    def __init__(self, cam_id = None, width = 640, height = 480):
        self.width = 640
        self.cam_id = cam_id
        self.width = width
        self.height = height

        # https://www.mygreatlearning.com/blog/yolo-object-detection-using-opencv/ 
        # https://github.com/AlexeyAB/darknet/releases/download/yolov4/yolov7-tiny.weights
        # https://github.com/AlexeyAB/darknet/blob/master/cfg/yolov7-tiny.cfg 
        self.model = cv2.dnn.readNet('models/yolov7-tiny.weights', 'models/yolov7-tiny.cfg')

        layer_names = self.model.getLayerNames()
        self.output_layers = [layer_names[i - 1] for i in self.model.getUnconnectedOutLayers()]

        self.classes = []
        # https://github.com/pjreddie/darknet/blob/master/data/coco.names 
        with open("coco.names", "r") as f:
            self.classes = [line.strip() for line in f.readlines()]

    def get_img(self):
        # https://github.com/unitreerobotics/UnitreecameraSDK/issues/12 
        IpLastSegment = "52"
        cam = self.cam_id
        udpstrPrevData = "udpsrc address=192.168.123."+ IpLastSegment + " port="
        udpPORT = [9201,9202,9203,9204,9205]
        # https://stackoverflow.com/questions/77446163/gstreamer-gstreamer-cant-find-avdec-h264-brew-cant-install-gst-libav-anymore 
        # udpstrBehindData = " ! application/x-rtp,media=video,encoding-name=H264 ! rtph264depay ! h264parse ! decodebin ! videoconvert ! queue ! appsink"
        # https://gstreamer.freedesktop.org/documentation/applemedia/vtdec.html?gi-language=c#vtdec 
        # udpstrBehindData = " ! application/x-rtp,media=video,encoding-name=H264 ! rtph264depay ! h264parse ! decodebin ! videoconvert ! autovideosink sync=false"
        # https://stackoverflow.com/questions/52879501/using-gstreamer-with-python-opencv-to-capture-live-stream 
        # https://stackoverflow.com/questions/69137752/gstreamer-appsink-is-much-more-slower-than-filesink 
        # appsink syncs to the clock 
        # when you use appsink the buffers will be synchronized to the pipeline clock - this will make your pipeline run in real-time (and not faster) 
        udpstrBehindData = " ! application/x-rtp,media=video,encoding-name=H264 ! rtph264depay ! h264parse ! decodebin ! videoconvert ! appsink drop=1" # works 

        udpSendIntegratedPipe_0 = udpstrPrevData +  str(udpPORT[cam-1]) + udpstrBehindData
        print(udpSendIntegratedPipe_0)        

        self.cap = cv2.VideoCapture(udpSendIntegratedPipe_0, cv2.CAP_GSTREAMER)

        if not self.cap.isOpened():
            raise Exception("Could not open video device")

    def demo(self):
        self.get_img()    
        while(True):
            self.ret, self.frame = self.cap.read()
            # print(f"ret: {self.ret}, frame: {self.frame}")
            if self.frame is None:
                break
            self.frame = cv2.resize(self.frame, (self.width, self.height))
            if self.cam_id == 1 or self.cam_id == 3 or self.cam_id == 4: 
                self.frame = cv2.flip(self.frame, -1)

            # https://github.com/AlexeyAB/darknet/blob/master/cfg/yolov7-tiny.cfg 
            # width=416, height=416
            self.model.setInput(cv2.dnn.blobFromImage(self.frame, 1 / 255.0, size=(416, 416), swapRB=True, crop=False))
            output = self.model.forward(self.output_layers)

            class_ids = []
            confidences = []
            boxes = []
            for out in output:
                for detection in out:
                    scores = detection[5:]
                    class_id = np.argmax(scores)
                    confidence = scores[class_id]
                    if confidence > .5:
                        # Object detected
                        center_x = int(detection[0] * self.width)
                        center_y = int(detection[1] * self.height)
                        w = int(detection[2] * self.width)
                        h = int(detection[3] * self.height)

                        # Rectangle coordinates
                        x = int(center_x - w / 2)
                        y = int(center_y - h / 2)

                        boxes.append([x, y, w, h])
                        confidences.append(float(confidence))
                        class_ids.append(class_id)

            indexes = cv2.dnn.NMSBoxes(boxes, confidences, 0.5, 0.4)
            colors = np.random.uniform(0, 255, size=(len(self.classes), 3))
            for i in range(len(boxes)):
                if i in indexes:
                    x, y, w, h = boxes[i]
                    label = str(self.classes[class_ids[i]])
                    color = colors[class_ids[i]]
                    cv2.rectangle(self.frame, (x, y), (x + w, y + h), color, 2)
                    cv2.putText(self.frame, label, (x, y -5),cv2.FONT_HERSHEY_SIMPLEX,
                    1/2, color, 2)

            if self.frame is not None:
                cv2.imshow("video0", self.frame)
            if cv2.waitKey(2) & 0xFF == ord('q'):
                break
        self.cap.release()
        cv2.destroyAllWindows()

if __name__ == "__main__":
    cam = camera(1)
    cam.demo()