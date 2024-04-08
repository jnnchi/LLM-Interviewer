from flask import Flask, request, jsonify, render_template
from openai import OpenAI
import requests
import sentiment_text_helpers
from pydub import AudioSegment
from google.cloud import storage # pip install google-cloud-storage 
from subprocess import call

app = Flask(__name__)
openai_client = OpenAI(api_key='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')
hf_api_url = "https://api-inference.huggingface.co/models/SamLowe/roberta-base-go_emotions"
headers = {"Authorization": "Bearer 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"}

def query(payload):
    response = requests.post(hf_api_url, headers=headers, json=payload)
    return response.json()

def analyze_tone(user_response):
    # this is where the output emotion is generated
    output = query({
        "inputs": user_response.lower(),
    })

    # this next variable is where all the possible feedback functions are added into
    feedback = (
        sentiment_text_helpers.system_messages[output[0][0]['label']]
        + sentiment_text_helpers.flag_overused_words(user_response.lower())
        + sentiment_text_helpers.flag_disallowed_words(user_response.lower())
        + sentiment_text_helpers.flag_um(user_response.lower())
    )

    return feedback

def generate_questions(input_prompt):
    with open('/Users/jennifer/VSCodeProjects/LLM-Interviewer/openai_practice/jennifer_template.txt', 'r') as file:
        template = file.read()

    # when user enters a new sentence, they won't type "Sentence: " first, so we do that
    input_prompt = 'Sentence: ' + input_prompt
    # pass the input prompt AND the template into the completions create function
    prompt = template + input_prompt
    # more tokens means longer responses, higher temperature means more creative responses
    completion = openai_client.completions.create(model='gpt-3.5-turbo-instruct', prompt=str(prompt), max_tokens=64, temperature=0.7)
    
    # extract the text section of completion object
    message = completion.choices[0].text
    
    output_list = message.split('\n')
    out_index = []
    for idx, sentence in enumerate(output_list):
        if 'Question' in sentence:
            out_index.append(idx)
    if out_index:
        return output_list[min(out_index):max(out_index) + 1]

@app.route('/analyze_transcript', methods=['POST']) 
def analyze_transcript():
    # get data from speech recognition
    data = request.json
    transcript = data['transcript']

    # run question gen on transcript
    questions = f"Next interview question: {generate_questions(transcript)}"
    # run tone analysis
    tone_analyzis = f"Your tone result: {analyze_tone(transcript)}"

    return jsonify({'message': 'Transcript received', 'questions': questions, 'tone analysis': tone_analyzis})

# homepage
@app.route('/')
def index():
    return render_template('index.html')


@app.route('/whisper', methods=['POST']) 
def transcribe_audio():
    """Takes a file path for an audio file and transcribes it into a string"""
    
    if 'audio_data' not in request.files:
        return jsonify({'message': 'No file part'}), 400

    # https://werkzeug.palletsprojects.com/en/3.0.x/datastructures/
    # audio file is type werkzeug.datastructures.file_storage.FileStorage
    # has attributes .stream, .filename, .content_type
    # has method .read() that reads it to bytes
    audio_file = request.files['audio_data']

    # initially save to webm (that's the type it's sent in too)
    audio_file.save(dst='audio.webm')

    # convert webm to wav using call function
    call(['ffmpeg', '-i', 'audio.webm', '-ar', '16000', '-ac', '1', 'audio.wav'])

    # no longer using; can just open file directly
    # wav_file = AudioSegment.from_file(file="audio.wav", format="wav")
    
    with open('audio.wav', 'rb') as audio_file:
        transcript = openai_client.audio.transcriptions.create(
            model="whisper-1",
            file=audio_file,
        )
    
    transcript = transcript.text

    # run question gen on transcript
    questions = f"Next interview question: {generate_questions(transcript)}"
    # run tone analysis
    tone_analyzis = f"Your tone result: {analyze_tone(transcript)}"

    return jsonify({'message': 'Transcript received', 'transcript': transcript, 'questions': questions, 'tone analysis': tone_analyzis})


if __name__ == '__main__':
    app.run(port=7000, debug=True)