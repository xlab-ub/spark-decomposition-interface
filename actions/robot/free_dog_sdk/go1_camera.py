import os

import cv2
import numpy as np

class go1_camera:
    def __init__(self, cam_id=1, width=640, height=480, model_name="yolov7-tiny", label_name="coco.names", WIFI=False, IpLastSegment=52, main_thread=True, get_brightness=False, brightness_dim=10, brightness_threshold=0.4):
        self.main_thread = main_thread

        self.width = 640
        self.cam_id = cam_id
        self.width = width
        self.height = height

        self.get_brightness = get_brightness
        self.brightness_dim = brightness_dim 
        self.brightness_threshold = brightness_threshold

        current_dir = os.path.dirname(os.path.abspath(__file__))
        weights_path = os.path.join(current_dir, f'models/{model_name}.weights')
        cfg_path = os.path.join(current_dir, f'models/{model_name}.cfg')
        self.model = cv2.dnn.readNet(weights_path, cfg_path)

        layer_names = self.model.getLayerNames()
        self.output_layers = [layer_names[i - 1] for i in self.model.getUnconnectedOutLayers()]

        self.classes = []
        label_path = os.path.join(current_dir, f'{label_name}')
        with open(label_path, "r") as f:
            self.classes = [line.strip() for line in f.readlines()]
    
        if WIFI:
            udpstrPrevData = "udpsrc address=192.168.12."+ str(IpLastSegment) + " port="
        else:
            udpstrPrevData = "udpsrc address=192.168.123."+ str(IpLastSegment) + " port="
        udpPORT = [9201,9202,9203,9204,9205]
        udpstrBehindData = " ! application/x-rtp,media=video,encoding-name=H264 ! rtph264depay ! h264parse ! decodebin ! videoconvert ! appsink drop=1" 
        udpSendIntegratedPipe_0 = udpstrPrevData +  str(udpPORT[cam_id-1]) + udpstrBehindData
        self.cap = cv2.VideoCapture(udpSendIntegratedPipe_0, cv2.CAP_GSTREAMER)

        if not self.cap.isOpened():
            raise Exception("Could not open video device")
    
    def get_classes(self):
        return self.classes

    def run(self):
        # min_luminance = 1 
        # max_luminance = 0
        while True:
            self.ret, self.frame = self.cap.read()
            if self.frame is None:
                break
            self.frame = cv2.resize(self.frame, (self.width, self.height))
            if self.cam_id == 1 or self.cam_id == 3 or self.cam_id == 4: 
                self.frame = cv2.flip(self.frame, -1)
            
            if self.get_brightness:
                # https://github.com/imneonizer/How-to-find-if-an-image-is-bright-or-dark 
                # Convert color space to LAB format and extract L channel
                L, _, _ = cv2.split(cv2.cvtColor(cv2.resize(self.frame, (self.brightness_dim, self.brightness_dim)), cv2.COLOR_BGR2LAB))
                # Normalize L channel by dividing all pixel values with maximum pixel value
                L = L/np.max(L)
                # Return True if mean is greater than thresh else False
                L = np.mean(L) 
                # if L < min_luminance:
                #     min_luminance = L
                # if L > max_luminance:
                #     max_luminance = L
                # print(f"min_luminance: {min_luminance}, max_luminance: {max_luminance} L: {L}")
                self.brightness = L > self.brightness_threshold

                # https://stackoverflow.com/questions/59280375/how-to-get-luminance-gradient-of-an-image 
                # lum = cv2.cvtColor(self.frame, cv2.COLOR_BGR2HSV)[...,2]
                # lum = cv2.cvtColor(cv2.resize(self.frame, (self.brightness_dim, self.brightness_dim)), cv2.COLOR_BGR2HSV)[...,2]
                # lum = lum/np.max(lum)
                # print(np.mean(lum))

                # Convert the image to grayscale
                # gray_img = cv2.cvtColor(self.frame, cv2.COLOR_BGR2GRAY)


                # # Calculate luminance using the formula
                # # luminance = 0.299 * gray_img[:,:,2] + 0.587 * gray_img[:,:,1] + 0.114 * gray_img[:,:,0]
                # luminance = 0.299 * gray_img + 0.587 * gray_img + 0.114 * gray_img
                # luminance = luminance/np.max(luminance)
                # luminance = np.mean(luminance)
                # print(luminance)

            # https://github.com/AlexeyAB/darknet/blob/master/cfg/yolov7-tiny.cfg 
            # width=416, height=416
            self.model.setInput(cv2.dnn.blobFromImage(self.frame, 1 / 255.0, size=(416, 416), swapRB=True, crop=False))
            outputs = self.model.forward(self.output_layers)

            class_ids = []
            confidences = []
            boxes = []
            centers = []
            for output in outputs:
                for detection in output:
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
                        centers.append([detection[0], detection[1]])
            
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

            if self.get_brightness:
                yield boxes, confidences, class_ids, centers, self.frame, self.brightness
            else:
                yield boxes, confidences, class_ids, centers, self.frame

            if self.main_thread: 
                if self.frame is not None:
                    cv2.imshow("video0", self.frame)
                    if cv2.waitKey(2) & 0xFF == ord('q'):
                        break
            
        self.cap.release()
        if self.main_thread:
            cv2.destroyAllWindows()

if __name__ == "__main__":
    # go1_camera_module = go1_camera(1)
    get_brightness = False
    go1_camera_module = go1_camera(1, WIFI=True, IpLastSegment=208, get_brightness=get_brightness, brightness_dim=10, brightness_threshold=0.4)
    classes = go1_camera_module.get_classes()
    try: 
        camera_data_generator = go1_camera_module.run()

        if get_brightness:
            while True:
                # boxes, confidences, class_ids, centers, _, brightness = next(camera_data_generator)
                # for class_id, center in zip(class_ids, centers):
                #     print(classes[class_id], center, brightness)
                _, _, _, _, _, brightness = next(camera_data_generator)
                print(brightness)
        else:
            while True:
                boxes, confidences, class_ids, centers, _ = next(camera_data_generator)
                # print(boxes, confidences, class_ids, centers)
                for class_id, center in zip(class_ids, centers):
                    print(classes[class_id], center)
            
    except KeyboardInterrupt:
        print('interrupted!')
        go1_camera_module.cap.release()
        cv2.destroyAllWindows()
