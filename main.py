from fastapi import FastAPI, BackgroundTasks
from pydantic import BaseModel
import requests,json
from gtts import gTTS
import os
from io import BytesIO, RawIOBase
import time
import cloudinary
import cloudinary.uploader
from moviepy.editor import *
import tempfile

temp_files, temp_file_objs = [], []


def saveVideoToCloudinary(videoFile, topic_name):
	# Set up Cloudinary configuration
	cloudinary.config(
	  cloud_name="dt6nkqhrt",
	  api_key="675265663147775",
	  api_secret="D1tX9vUwL5KT4DUp3zDl8kg8Gw8"
	)

	with tempfile.NamedTemporaryFile(suffix='.mp4', delete = False) as tmp_file:
		tmp_filename = tmp_file.name
		print(tmp_filename)
		# Write the clip to the temporary file
		videoFile.write_videofile(tmp_filename, fps=30, bitrate="5000k")

		# Seek to the beginning of the file
		tmp_file.seek(0)

		# Read the contents of the file into a BytesIO object
		bytes_io = BytesIO(tmp_file.read())

		temp_files.append(tmp_filename)
		temp_file_objs.append(videoFile)


	response = cloudinary.uploader.upload(bytes_io, resource_type="auto", public_id=topic_name, folder="my_folder")
	print("File uploaded to cloudinary")
	return response['secure_url']


def convertGttsToAudioLib(gttsObj):
	with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as temp_file:
		# Write the audio data to the temporary file
		gttsObj.write_to_fp(temp_file)

		# Get the filename of the temporary file
		temp_filename = temp_file.name
		temp_files.append(temp_filename)

	print("Saved temp audio to ", temp_filename)
	return AudioFileClip(temp_filename)


def convertTextToAudioLib(text, language, topic_name):
	# Create an object
	speech = gTTS(text=text, lang=language, slow=False)

	# return AudioFileClip(filepath)
	audioLibFile = convertGttsToAudioLib(speech)
	temp_file_objs.append(audioLibFile)
	return audioLibFile


def getConcatenatedVideoForAudio(audio_file, videos_data):
	source_videos = []
	cur_duration = 0
	shouldEnd = False
	audio_duration = audio_file.duration
	start_times = []

	for i, video_data in enumerate(videos_data):
		start_times.append(cur_duration)
		video_url = video_data['video_files'][0]['link']

		response = requests.get(video_url)
		#Writing downloaded video to temp file
		with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as temp_file:
			temp_file.write(response.content)
			temp_filename = temp_file.name
			print("Wrote pexel video to " + temp_filename)
			temp_files.append(temp_filename)

		#Convert temp file to VideoFileClip
		videoClip = VideoFileClip(temp_filename).resize((640,480))
		temp_file_objs.append(videoClip)

		videoDuration = videoClip.duration

		if(cur_duration + videoDuration <= audio_duration):
			source_videos.append(videoClip)
		else:
			clippedVideo = videoClip.subclip(0, audio_duration - cur_duration)
			source_videos.append(clippedVideo)
			shouldEnd = True
		# #TODO:Removing temp file
		# os.remove(temp_filename)
		cur_duration +=videoDuration

		print(cur_duration, videoDuration, audio_duration)

		if shouldEnd:
			break

	# Create a composite video from the source video clips
	concatenated_video = concatenate_videoclips(source_videos)

	# Set the start times of the source video clips in the composite video
	for i in range(len(source_videos)):
		concatenated_video = concatenated_video.set_start(start_times[i])

	# Set the audio of the composite video to the audio of the audio file
	concatenated_video = concatenated_video.set_audio(audio_file)

	# # Export the composite video with the integrated audio
	# concatenated_video.write_videofile("output8.mp4", fps=30, bitrate="5000k")

	# for video in source_videos:
	# 	video.close()
	# audio_file.close()

	return concatenated_video

def getVideosFromPexel(video_genre):
	# Set up API key and topic
	API_KEY = 'iS0Zktr6w8jvUgaHk1VGgluFvSDMFH8TDpg6alxwAKXxpDCu6vqTcJk7'
	video_genre = video_genre

	# Set up API endpoint and parameters
	url = f'https://api.pexels.com/videos/search?query={video_genre}&per_page=20'
	headers = {'Authorization': API_KEY}

	# Send API request
	response = requests.get(url, headers=headers)
	# print(response)

	# Parse JSON response
	data = json.loads(response.text)
	print("Received response from pexel")
	return data['videos']

def convertAudioToVideo(audio_file, video_genre):
	pexelVideos = getVideosFromPexel(video_genre)
	# Extract video URLs and titles
	concatenatedVideoFileClip = getConcatenatedVideoForAudio(audio_file, pexelVideos)

	return concatenatedVideoFileClip

def cleanup_tmp_files():
	for fileObj in temp_file_objs:
		try:
			print("Closing file object")
			fileObj.close()
		except Exception as e:
			print("Closing file object failed", e)

	for file in temp_files:
		try:
			print("Removing "+file)
			os.remove(file)
		except Exception as e:
			print("File removal failed: ", e)

def create_audio_from_gpt(topic_name, video_genre):
	# Define the URL for the ChatGPT endpoint
	endpoint = "https://api.openai.com/v1/chat/completions"

	# Define parameters for the request

	topicsList = [topic_name]
	language = 'Hindi'

	access_token = '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'

	headers = {
		'Authorization': 'Bearer ' + access_token,
		'Content-Type': 'application/json'
	}
	# print(topicsList)
	for topic_name in topicsList:

		payload = {
			"model": "gpt-3.5-turbo",
			"messages": [
				{
					"role": "user",
					"content": "Generate text for a full length class on " + topic_name + "written in " + language
				}
			]
		}

		print("Requesting gpt for topic "+topic_name)
		response = requests.post(endpoint, json=payload, headers = headers)
		print("Received response from gpt for topic "+topic_name)

		map_resp = json.loads(response.text)
		# print(map_resp)

		videoContent = map_resp['choices'][0]['message']['content']
		# videoContent = topic_name
		# print(videoContent)
		# with open("content\\"+topic_name+"_"+language+".txt", mode="w", encoding='utf-8') as file:
		# 	file.write(videoContent)
		# print(topic_name + " file written")
		audio = convertTextToAudioLib(videoContent,'hi',topic_name)
		print(topic_name + " audio file generated")
		video = convertAudioToVideo(audio, video_genre)
		print(topic_name + " video file generated")
		cloudinaryLink = saveVideoToCloudinary(video, topic_name)
		print(topic_name + " video file saved on Cloudinary")

		cleanup_tmp_files()
		return cloudinaryLink


app = FastAPI()

class InputData(BaseModel):
	topic_name: str
	video_genre: str


@app.post("/process_input")
async def process_input(input_data: InputData, background_tasks: BackgroundTasks):
	# background_tasks.add_task(create_audio_from_gpt, input_data.input_str)
	# Replace this with your actual processing logic
	audioFileLink = create_audio_from_gpt(input_data.topic_name, input_data.video_genre)
	return {"video_file_link": audioFileLink}