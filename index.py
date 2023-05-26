
import urllib
import webapp3
import jinja2
from pytube import YouTube
from apiclient.discovery import build
from optparse import OptionParser
import cv2
from moviepy.editor import *
from moviepy.video.tools.subtitles import SubtitlesClip
from moviepy.video.tools.subtitles import file_to_subtitles
from moviepy.video.fx.all import crop
from google.cloud import speech_v1p1beta1 as speech
from pydub.utils import mediainfo
from google.oauth2 import service_account
from google.cloud import storage
import srt
from datetime import timedelta
import os
import whisper
import openai
from boto3 import Session
from srt_equalizer import srt_equalizer
import pandas as pd

  
# reading the csv file
df = pd.read_csv("movies.csv")

for index,row in df.iterrows():
    if(row['Used']==False):
        movie = row['Movie']
        used = row['Used']
        df.loc[index, 'Used'] = True
        df.to_csv("movies.csv", index=False)
        break


# Replace YOUR_API_KEY with your OpenAI API key
openai.api_key = ""


prompt = """Can you write a paragraph (in less than 600 characters) about an interesting information of the movie,""" + movie + """? The length of the paragraph must be more than 200 characters but less than 600 characters. The format you must follow in the answer is "The fun fact: Did you know..." """


# Generate a response
response = openai.ChatCompletion.create(
    model='gpt-3.5-turbo',
      messages=[
        {"role": "user", "content": prompt}],
    max_tokens=1024,
    temperature=0,
)
# Print the response
prompt = response.choices[0].message.content

funfact = prompt.split("The fun fact:",1)[1].strip()



trailer_search = movie + " HD Scene"
trailer_file = movie + "Trailer"

audio_file = movie + ".mp3"
subt_file = movie + ".srt"
movie_final_file = movie + ".mp4"

SCOPES = ["https://www.googleapis.com/auth/cloud-platform"]
os.environ["GOOGLE_APPLICATION_CREDENTIALS"]="famous-athlete-383112-b4d8877db955.json"
SERVICE_ACCOUNT_FILE = 'famous-athlete-383112-b4d8877db955.json'
storage_client = storage.Client.from_service_account_json(SERVICE_ACCOUNT_FILE)

creds = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE, scopes=SCOPES)

# Set DEVELOPER_KEY to the "API key" value from the Google Developers Console:
# https://console.developers.google.com/project/_/apiui/credential
# Please ensure that you have enabled the YouTube Data API for your project.
DEVELOPER_KEY = ""
YOUTUBE_API_SERVICE_NAME = "youtube"
YOUTUBE_API_VERSION = "v3"
BUCKET_NAME = "youtubestorage"

youtube = build(
            YOUTUBE_API_SERVICE_NAME, 
            YOUTUBE_API_VERSION, 
            developerKey=DEVELOPER_KEY)
search_response = youtube.search().list(
            q=trailer_search,
            part="id,snippet",
            maxResults=1
          ).execute()
        
for item in search_response['items']:
    param = item['id']['videoId']


link = "https://www.youtube.com/watch?v=" + param

def transcribe_audio(path,subt_file):
    model = whisper.load_model("base") # Change this to your desired model
    print("Whisper model loaded.")
    transcribe = model.transcribe(audio=path)
    segments = transcribe['segments']

    for segment in segments:
        startTime = str(0)+str(timedelta(seconds=int(segment['start'])))+',000'
        endTime = str(0)+str(timedelta(seconds=int(segment['end'])))+',000'
        text = segment['text']
        segmentId = segment['id']+1
        segment = f"{segmentId}\n{startTime} --> {endTime}\n{text[1:] if text[0] == ' ' else text}\n\n"

        with open(subt_file, 'a', encoding='utf-8') as srtFile:
            srtFile.write(segment)
        
def Download(link):
    youtubeObject = YouTube(link)
    youtubeObject = youtubeObject.streams.get_highest_resolution()
    try:
        youtubeObject.download(filename=trailer_file)
    except:
        print("An error has occurred")
    print("Download is completed successfully")


Download(link)



session = Session(
    aws_access_key_id="",
    aws_secret_access_key="",
    region_name = 'us-west-2'
)
polly = session.client("polly")


 # Request speech synthesis
response = polly.synthesize_speech(Text=funfact, OutputFormat="mp3",
                                        VoiceId="Joanna", TextType='text')
file = open(audio_file, 'wb')
file.write(response['AudioStream'].read())
file.close()



audioClip = AudioFileClip(audio_file)
duration_voice = audioClip.duration




clip = VideoFileClip(trailer_file)
(w, h) = clip.size

crop_width = h * 9/16
# x1,y1 is the top left corner, and x2, y2 is the lower right corner of the cropped area.

x1, x2 = 0, h
y1, y2 = 0, h
cropped_clip = crop(clip, x1=x1, y1=y1, x2=x2, y2=y2)
duration = clip.duration

cropped_clip = cropped_clip.subclip((duration/2-duration_voice),(duration/2))

cropped_clip = cropped_clip.without_audio()

cropped_clip = (cropped_clip
    .set_audio(audioClip)
    .volumex(2)
    .audio_fadein(1.0)
    .audio_fadeout(1.0)
)

# or you can specify center point and cropped width/height
# cropped_clip = crop(clip, width=crop_width, height=h, x_center=w/2, y_center=h/2)



transcribe_audio(audio_file,subt_file)
srt_equalizer.equalize_srt_file(subt_file, movie + "_shortened.srt", 42)
(ww, hh) = cropped_clip.size
subtitletype = lambda txt: TextClip(txt, font='Lane', fontsize=30, color='white', bg_color="black", method='caption', align='south', size=(ww,0))
sub = SubtitlesClip(movie + "_shortened.srt", subtitletype)
print(clip.size)
print(cropped_clip.size)
result = CompositeVideoClip([cropped_clip, sub.set_pos(('center','bottom')).margin(bottom=100, opacity=0)])

result.write_videofile(movie_final_file)
