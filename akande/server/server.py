import cherrypy
import json
import logging
import os
import io
import speech_recognition as sr
from pydub import AudioSegment
from pydub.exceptions import CouldntDecodeError
from akande.config import OPENAI_DEFAULT_MODEL
from akande.services import OpenAIImpl


class AkandeServer:
    def __init__(self):
        self.openai_service = OpenAIImpl()
        self.logger = logging.getLogger(__name__)

    @cherrypy.expose
    def index(self):
        return open("./public/index.html")

    @cherrypy.expose
    def static(self, path):
        return open(f"./public/{path}")

    @cherrypy.expose
    def process_question(self):
        try:
            request_data = json.loads(cherrypy.request.body.read())
            question = request_data.get("question")
            self.logger.info(f"Received question: {question}")

            response_object = (
                self.openai_service.generate_response_sync(
                    question, OPENAI_DEFAULT_MODEL, None
                )
            )
            message_content = response_object.choices[0].message.content
            return json.dumps({"response": message_content})

        except Exception as e:
            self.logger.error(f"Failed to process question: {e}")
            return json.dumps({"response": "An error occurred"})

    @cherrypy.expose
    @cherrypy.tools.allow(methods=["POST"])
    def process_audio_question(self):
        try:
            audio_data = cherrypy.request.body.read()
            wav_file_path = self.convert_to_wav(audio_data)
            processed_result = self.process_audio(wav_file_path)

            question_data = {
                "response": "Audio data processed successfully",
                "result": processed_result,
            }

            question = question_data.get("result").get("text")
            response_object = (
                self.openai_service.generate_response_sync(
                    question, OPENAI_DEFAULT_MODEL, None
                )
            )

            if os.path.exists(wav_file_path):
                os.remove(wav_file_path)
                self.logger.info(f"WAV file removed: {wav_file_path}")

            message_content = response_object.choices[0].message.content
            return json.dumps({"response": message_content})

        except Exception as e:
            self.logger.error("Failed to process audio:", exc_info=True)
            cherrypy.response.status = 500
            return json.dumps(
                {"error": "Failed to process audio", "details": str(e)}
            ).encode("utf-8")

    @staticmethod
    def convert_to_wav(audio_data):
        try:
            for input_format in ["webm", "mp3", "mp4", "ogg", "flac"]:
                try:
                    audio_segment = AudioSegment.from_file(
                        io.BytesIO(audio_data), format=input_format
                    )
                    break
                except CouldntDecodeError:
                    pass

            else:
                raise ValueError("Unsupported audio format")

            audio_segment = audio_segment.set_channels(
                1
            ).set_frame_rate(16000)
            directory_path = "./"
            filename = "audio.wav"
            file_path = os.path.join(directory_path, filename)
            audio_segment.export(file_path, format="wav")
            return file_path

        except Exception as e:
            raise RuntimeError(f"Error converting audio: {e}")

    @staticmethod
    def process_audio(file_path):
        try:
            recognizer = sr.Recognizer()
            with sr.AudioFile(file_path) as source:
                audio_data = recognizer.record(source)

            text = recognizer.recognize_google(audio_data)
            return {"text": text, "success": True}

        except sr.UnknownValueError:
            return {
                "error": "Audio could not be understood",
                "success": False,
            }
        except sr.RequestError as e:
            return {
                "error": f"Speech recognition service error {e}",
                "success": False,
            }


def main():
    logging.basicConfig(level=logging.INFO)
    cherrypy.config.update({"server.socket_port": 8080})
    cherrypy.quickstart(AkandeServer())


if __name__ == "__main__":
    main()
