try:
    import cv2
except ImportError:
    import logging
    logging.warning("cv2 (opencv-python) module not found. Video effects will not work.")
    cv2 = None

import numpy as np
from typing import List

class EffectAdder:
    @staticmethod
    def add_transition(input_path: str, output_path: str, effect_type: str = "fade"):
        """添加转场特效"""
        if cv2 is None:
            raise ImportError("cv2 is required for video effects but is not installed")

        cap = cv2.VideoCapture(input_path)
        fps = cap.get(cv2.CAP_PROP_FPS)
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        
        # 创建输出视频
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out = cv2.VideoWriter(output_path, fourcc, fps, (1080, 1920))
        
        # 添加淡入淡出
        for i in range(frame_count):
            ret, frame = cap.read()
            if not ret:
                break
                
            if effect_type == "fade":
                # 前30帧淡入
                if i < 30:
                    alpha = i / 30
                    frame = cv2.addWeighted(
                        np.zeros_like(frame), 1-alpha,
                        frame, alpha, 0
                    )
                # 最后30帧淡出
                elif i > frame_count - 30:
                    alpha = (frame_count - i) / 30
                    frame = cv2.addWeighted(
                        np.zeros_like(frame), 1-alpha,
                        frame, alpha, 0
                    )
                    
            out.write(frame)
            
        cap.release()
        out.release()
