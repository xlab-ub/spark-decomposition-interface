import cv2
# print(cv2.getBuildInformation())

# https://www.google.com/search?q=cv2+dnn+fastest+object+detection&newwindow=1&sca_esv=582856167&ei=Go9VZYnIHJa0ptQP7_-EmAU&ved=0ahUKEwiJvda2zMeCAxUWmokEHe8_AVMQ4dUDCBA&uact=5&oq=cv2+dnn+fastest+object+detection&gs_lp=Egxnd3Mtd2l6LXNlcnAiIGN2MiBkbm4gZmFzdGVzdCBvYmplY3QgZGV0ZWN0aW9uMgUQIRigATIFECEYqwIyBRAhGKsCMgUQIRirAjIIECEYFhgeGB0yCBAhGBYYHhgdMggQIRgWGB4YHUjnLFCqBli6K3ACeAGQAQCYAWGgAe0PqgECMja4AQPIAQD4AQHCAgoQABhHGNYEGLADwgIHEAAYigUYQ8ICCBAAGIoFGJECwgIFEAAYgATCAgYQABgWGB7CAggQABiKBRiGA-IDBBgAIEGIBgGQBgg&sclient=gws-wiz-serp 
# Pretrained classes in the model
classNames = {0: 'background',
              1: 'person', 2: 'bicycle', 3: 'car', 4: 'motorcycle', 5: 'airplane', 6: 'bus',
              7: 'train', 8: 'truck', 9: 'boat', 10: 'traffic light', 11: 'fire hydrant',
              13: 'stop sign', 14: 'parking meter', 15: 'bench', 16: 'bird', 17: 'cat',
              18: 'dog', 19: 'horse', 20: 'sheep', 21: 'cow', 22: 'elephant', 23: 'bear',
              24: 'zebra', 25: 'giraffe', 27: 'backpack', 28: 'umbrella', 31: 'handbag',
              32: 'tie', 33: 'suitcase', 34: 'frisbee', 35: 'skis', 36: 'snowboard',
              37: 'sports ball', 38: 'kite', 39: 'baseball bat', 40: 'baseball glove',
              41: 'skateboard', 42: 'surfboard', 43: 'tennis racket', 44: 'bottle',
              46: 'wine glass', 47: 'cup', 48: 'fork', 49: 'knife', 50: 'spoon',
              51: 'bowl', 52: 'banana', 53: 'apple', 54: 'sandwich', 55: 'orange',
              56: 'broccoli', 57: 'carrot', 58: 'hot dog', 59: 'pizza', 60: 'donut',
              61: 'cake', 62: 'chair', 63: 'couch', 64: 'potted plant', 65: 'bed',
              67: 'dining table', 70: 'toilet', 72: 'tv', 73: 'laptop', 74: 'mouse',
              75: 'remote', 76: 'keyboard', 77: 'cell phone', 78: 'microwave', 79: 'oven',
              80: 'toaster', 81: 'sink', 82: 'refrigerator', 84: 'book', 85: 'clock',
              86: 'vase', 87: 'scissors', 88: 'teddy bear', 89: 'hair drier', 90: 'toothbrush'}

def id_class_name(class_id, classes):
    for key,value in classes.items():
        if class_id == key:
            return value

class camera:
    def __init__(self, cam_id = None, width = 640, height = 480):
        self.width = 640
        self.cam_id = cam_id
        self.width = width
        self.height = height

        self.model = cv2.dnn.readNetFromTensorflow('models/frozen_inference_graph.pb', 'models/ssd_mobilenet_v2_coco_2018_03_29.pbtxt') 


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

            self.model.setInput(cv2.dnn.blobFromImage(self.frame, size=(300, 300), swapRB=True))
            output = self.model.forward()
            for detection in output[0, 0, :, :]:
                confidence = detection[2]
                if confidence > .5:
                    class_id = detection[1]
                    class_name = id_class_name(class_id, classNames)
                    # print(str(str(class_id) + " " + str(detection[2])  + " " + id_class_name(class_id,classNames)))
                    print(str(str(class_id) + " " + str(detection[2])  + " " + class_name)) 

                    image_height, image_width, _ = self.frame.shape 

                    box_x = detection[3] * image_width
                    box_y = detection[4] * image_height
                    box_width = detection[5] * image_width
                    box_height = detection[6] * image_height

                    cv2.rectangle(self.frame, (int(box_x), int(box_y)), (int(box_width), int(box_height)), (23, 230, 210), thickness=1)

                    cv2.putText(self.frame, class_name ,(int(box_x), int(box_y+.05*image_height)),cv2.FONT_HERSHEY_SIMPLEX,(.005*image_width),(0, 0, 255)) 

            if self.frame is not None:
                cv2.imshow("video0", self.frame)
            if cv2.waitKey(2) & 0xFF == ord('q'):
                break
        self.cap.release()
        cv2.destroyAllWindows()

if __name__ == "__main__":
    cam = camera(1)
    cam.demo()