"""Server-side OCR and Arabic overlay before WebRTC encoding. Video-only MVP."""
import asyncio
import logging
import os
import time
from aiortc import VideoStreamTrack
from av import VideoFrame
from PIL import ImageDraw, ImageFont
import arabic_reshaper
from bidi.algorithm import get_display


class SubtitleTrack(VideoStreamTrack):
    def __init__(self, source, translate, read_text):
        super().__init__()
        self.source, self.translate, self.read_text = source, translate, read_text
        self.last_ocr = 0
        self.task = None
        self.subtitle = ''
        self.font = ImageFont.truetype(os.getenv('ARABIC_FONT','/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'), 27)

    async def recognize(self, image):
        try:
            # Read bottom dialogue area; configurable ratio, not emulator memory.
            ratio = min(.9, max(0, float(os.getenv('OCR_CROP_TOP','0.55'))))
            crop = image.crop((0,int(image.height*ratio),image.width,image.height))
            text = await asyncio.to_thread(self.read_text,crop)
            self.subtitle = await self.translate(text) if text else ''
        except Exception:
            self.subtitle = ''
            logging.exception('OCR/translation failed; stream continues without subtitles')

    async def recv(self):
        frame = await self.source.recv()
        image = frame.to_image()
        now = time.monotonic()
        if now-self.last_ocr >= 3 and (not self.task or self.task.done()):
            self.last_ocr = now
            self.task = asyncio.create_task(self.recognize(image.copy()))
        if self.subtitle:
            draw = ImageDraw.Draw(image)
            # Wrap logical Arabic before reshaping each line.
            lines, line = [], ''
            for word in self.subtitle.split():
                candidate = (line+' '+word).strip()
                visual = get_display(arabic_reshaper.reshape(candidate))
                if draw.textlength(visual,font=self.font) > image.width-80 and line:
                    lines.append(line)
                    line = word
                else:
                    line = candidate
            if line:
                lines.append(line)
            lines = lines[:3]
            y = image.height - 25 - len(lines)*37
            draw.rectangle((20,y-9,image.width-20,image.height-15), fill=(13,11,19))
            for line in lines:
                visual = get_display(arabic_reshaper.reshape(line))
                w = draw.textlength(visual,font=self.font)
                draw.text(((image.width-w)/2,y),visual,font=self.font,fill='white')
                y += 37
        result = VideoFrame.from_image(image)
        result.pts, result.time_base = frame.pts, frame.time_base
        return result

    def stop(self):
        if self.task:
            self.task.cancel()
        self.source.stop()
        super().stop()
