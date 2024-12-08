import cv2
import mediapipe as mp
import numpy as np
import tensorflow as tf
from keras.models import load_model
# above is the import method for tensorflow 2.15.0 and keras 2.15.0
# for keras 3.6.0 and tensorflow 2.17.0, the method is from keras.src.saving import load_model
# I downgraded the tensorflow library and also the python version in order for tensorflowjs to work.
import time

# load my model :)
model = load_model('v2_afrafck_model/thisworks.h5')

# convert a frame in to a square (fill empty space with some black color)
def expand_to_square(image):
    h, w, _ = image.shape
    if h == w:
        return image
    if h < w:
        diff = w - h
        fill = diff // 6
        top = fill
        bottom = fill
        new_image = cv2.copyMakeBorder(image, top, bottom, 0, 0, cv2.BORDER_CONSTANT, value=[0, 0, 0])
        new_image = cv2.resize(new_image, (w, w))
    else:
        diff = h - w
        fill = diff // 6
        left = fill
        right = fill
        new_image = cv2.copyMakeBorder(image, 0, 0, left, right, cv2.BORDER_CONSTANT, value=[0, 0, 0])
        new_image = cv2.resize(new_image, (h, h))
    return new_image
global emotion_val
global not_stressed_val
global stressed_val
global steps_print_val
global face_distance
global stress_status
face_distance = 12
stress_status = 0
emotion_val=0
def reset_values_by_Bach():
    global emotion_val
    emotion_val=0
    global not_stressed_val
    not_stressed_val=0
    global stressed_val
    stressed_val=0
    global steps_print_val
    steps_print_val=0
    global stress_status
    stress_status = 0
reset_values_by_Bach()



mp_face_mesh = mp.solutions.face_mesh
cap = cv2.VideoCapture(0)
with mp_face_mesh.FaceMesh(
    max_num_faces=1,
    refine_landmarks=True,
    min_detection_confidence=0.75,
    min_tracking_confidence=0.75) as face_mesh:
  while cap.isOpened():
    success, image = cap.read()
    if not success:
      print("Ignoring empty camera frame.")
      cap = cv2.VideoCapture(0)
      continue

    # Imagewritable = False to improve performance
    image.flags.writeable = False
    image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    # flip the frame for selfie view :)
    image = cv2.flip(image, 1)
    results = face_mesh.process(image)

    # calculate the position which has the face and draw a cool face tracking frame.
    image.flags.writeable = True
    image = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
    if results.multi_face_landmarks:
        for face_landmarks in results.multi_face_landmarks:
            
            h, w, c = image.shape
            cx_min, cy_min = w, h
            cx_max, cy_max = 0, 0
            for lm in face_landmarks.landmark:
                cx, cy = int(lm.x * w), int(lm.y * h)
                if cx < cx_min:
                    cx_min = cx
                if cy < cy_min:
                    cy_min = cy
                if cx > cx_max:
                    cx_max = cx
                if cy > cy_max:
                    cy_max = cy
            
            # settings for the cool face tracking sign :)
            side_length_x = int(0.4 * (cx_max - cx_min))
            side_length_y = int(0.4 * (cy_max - cy_min))
            longer_side = max(cx_max - cx_min, cy_max - cy_min)
            thickness = int(0.07 * longer_side)
            
            # draw the top right corner of the sign
            cv2.line(image, (cx_max, cy_min), (cx_max - side_length_x, cy_min), (255, 255, 0), thickness)
            cv2.line(image, (cx_max, cy_min), (cx_max, cy_min + side_length_y), (255, 255, 0), thickness)
        
            # draw bottom left corner
            cv2.line(image, (cx_min, cy_max), (cx_min + side_length_x, cy_max), (255, 255, 0), thickness)
            cv2.line(image, (cx_min, cy_max), (cx_min, cy_max - side_length_y), (255, 255, 0), thickness)

        # extract the face region using the coordinates above
        face_region = image[cy_min:cy_max, cx_min:cx_max]
        if face_region.size > 0:

            """ before we cut out the frame and convert to a square frame,
                we need to calculate the distance between the face and the camera.

                After we have the distance, we can warn user if they are not focus on their work.
            """
            frameWidth = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            frameHeight = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            camera_size = frameWidth*frameHeight
            distance = (((cx_max-cx_min)*(cy_max-cy_min))*100//camera_size)
            cv2.putText(image, str(distance), (cx_min, cy_min - 120), cv2.FONT_HERSHEY_SIMPLEX, 3, (255, 255, 0), 10, cv2.LINE_AA)
            if distance <=7:
                cv2.putText(image, 'Too far from the screen, please stay closer to lock in!', (cx_min-600, cy_min - 180), cv2.FONT_HERSHEY_SIMPLEX, 2, (255, 255, 0), 1, cv2.LINE_AA)
            if distance >17:
                cv2.putText(image, 'Too close to the screen, lean back or you will harm your eyes', (cx_min-650, cy_min - 180), cv2.FONT_HERSHEY_SIMPLEX, 2, (255, 255, 0), 1, cv2.LINE_AA)


            if distance >7 and distance <=17:
                face_region = expand_to_square(face_region)
                # resize the face region to 224x224 (bc we trained the model on 224x224 images) (now 160x160 new model)
                face_region = cv2.resize(face_region, (160, 160))
                # convert to grayscale before feeding into the model :)
                face_region_gray = cv2.cvtColor(face_region, cv2.COLOR_BGR2GRAY)
                face_region_gray = np.expand_dims(face_region_gray, axis=-1)
                face_region_gray = np.expand_dims(face_region_gray, axis=0)
                face_region_gray = face_region_gray / 255.0

                # predict
                emotion_prediction = model.predict(face_region_gray)

                # labels
                emotion_dict = {0: 'Neutral', 1: 'Happy', 2: 'Sad', 3: 'Surprise', 4: 'Fear', 5: 'Disgusted', 6: 'Angry'}

                # get sorted emotions with the according confidence
                sorted_emotions = sorted(zip(emotion_dict.values(), emotion_prediction[0]), key=lambda x: x[1], reverse=True)

                # settings for the information that is displayed on the top left corner :)
                start_x, start_y = 50, 100
                bar_height = 30
                bar_width = 200
                spacing = 20
                text_offset = 100

                # grey rounded rectangle background with 80% opacity (Something like high-tech UI :) )
                bg_top_left = (start_x - 30, start_y - 60)
                bg_bottom_right = (start_x + bar_width + text_offset + 330, start_y + len(sorted_emotions) * (bar_height + spacing))

                # create an overlay image
                overlay = image.copy()
                cv2.rectangle(overlay, bg_top_left, bg_bottom_right, (94, 94, 94), -1, cv2.LINE_AA)

                # blend the overlay with the original image
                opacity = 0.8  # opacity factor
                cv2.addWeighted(overlay, opacity, image, 1 - opacity, 0, image)

                # the most confident detected emotion above our faces :) (I set only one face at a time)
                most_confident_emotion = sorted_emotions[0][0]
                cv2.putText(image, most_confident_emotion, (cx_min, cy_min - 40), cv2.FONT_HERSHEY_SIMPLEX, 3, (255, 255, 0), 10, cv2.LINE_AA)

                if most_confident_emotion in ['Happy', 'Neutral', 'Surprise']:
                    stressed_val+=1
                    steps_print_val+=1
                else:
                    stressed_val-=1
                    steps_print_val+=1
                emotion_val=stressed_val/steps_print_val
                emotion_val=stressed_val/steps_print_val

                if (steps_print_val==25) and emotion_val<=(0.3):
                    stress_status = 1
                    start_time = time.time()
                    print()
                    print()
                    print(start_time)
                    print('You are stressed!!!')
                    print('Please relax a little bit!')
                
                    
                if (steps_print_val>25) and emotion_val>(0.3):
                    reset_values_by_Bach()
                if stress_status == 1:
                    end_time = time.time()
                    print()
                    print(end_time)
                    cv2.putText(image, 'You are stressed!', (cx_min, cy_min - 180), cv2.FONT_HERSHEY_SIMPLEX, 3, (255, 255, 0), 10, cv2.LINE_AA)
                    print(end_time-start_time)
                    if end_time - start_time >= 1:
                        reset_values_by_Bach()
                cv2.putText(image, str(emotion_val), (cx_min, cy_min - 280), cv2.FONT_HERSHEY_SIMPLEX, 3, (255, 255, 0), 10, cv2.LINE_AA)
                
                # info on the top left corner
                for i, (emotion, confidence) in enumerate(sorted_emotions):
                    # display emotion texts
                    text_position = (start_x, start_y + i * (bar_height + spacing))
                    cv2.putText(image, emotion, text_position, cv2.FONT_HERSHEY_SIMPLEX, 1.2, (255, 255, 0), 2, cv2.LINE_AA)
                    
                    # confidence bar
                    bar_length = int(bar_width * confidence)
                    bar_position = (start_x + text_offset + 140, start_y + i * (bar_height + spacing) - 25)
                    cv2.rectangle(image, bar_position, (bar_position[0] + bar_length, bar_position[1] + bar_height), (255, 255, 0), -1, cv2.LINE_AA)
                    
                    # percentages next to the bars :)
                    confidence_text = f"{confidence * 100:.2f}%"
                    confidence_position = (bar_position[0] + bar_length + 10, bar_position[1] + bar_height -5)
                    cv2.putText(image, confidence_text, confidence_position, cv2.FONT_HERSHEY_SIMPLEX, 1.2, (255, 255, 0), 2, cv2.LINE_AA)

    cv2.imshow('Bach-emotion-detect', image)
    if cv2.waitKey(5) & 0xFF == 27:
        break
cap.release()
cv2.destroyAllWindows()
