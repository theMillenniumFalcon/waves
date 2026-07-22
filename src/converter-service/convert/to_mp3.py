import json
import os
import tempfile

import pika
from bson.objectid import ObjectId
from moviepy import VideoFileClip


def start(message, fs_videos, fs_mp3s, channel):
    message = json.loads(message)

    # Create a temporary file for the downloaded video
    tf = tempfile.NamedTemporaryFile(delete=False)
    try:
        # Read video from GridFS
        out = fs_videos.get(ObjectId(message["video_fid"]))
        tf.write(out.read())
        tf.close()

        # Extract audio
        tf_path = os.path.join(
            tempfile.gettempdir(),
            f"{message['video_fid']}.mp3",
        )

        with VideoFileClip(tf.name) as clip:
            clip.audio.write_audiofile(tf_path)

        # Save MP3 to GridFS
        with open(tf_path, "rb") as f:
            fid = fs_mp3s.put(f.read())

        os.remove(tf_path)
        os.remove(tf.name)

        message["mp3_fid"] = str(fid)

        try:
            channel.basic_publish(
                exchange="",
                routing_key=os.environ.get("MP3_QUEUE"),
                body=json.dumps(message),
                properties=pika.BasicProperties(
                    delivery_mode=pika.spec.PERSISTENT_DELIVERY_MODE
                ),
            )
        except Exception:
            fs_mp3s.delete(fid)
            return "failed to publish message"

    finally:
        # Ensure temporary video file is removed
        if os.path.exists(tf.name):
            os.remove(tf.name)