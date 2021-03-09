import json
import logging
import re
import sys
from pathlib import Path
from typing import List, NamedTuple

import requests
from slugify import slugify

from kadenze_dl.progress import progress

logger = logging.getLogger("helpers")
logger.addHandler(logging.StreamHandler(sys.stdout))
logger.setLevel(logging.INFO)

filename_pattern = re.compile("file/(.*\.mp4)\?")


class Session(NamedTuple):
    course: str
    index: int
    name: str
    path: str


class Video(NamedTuple):
    session: Session
    index: int
    title: str
    url: str


def format_course(course: str) -> str:
    formatted_course = course.split("/")[-1]
    return f"{formatted_course}"


def extract_filename(video_url: str) -> str:
    filename = re.search(filename_pattern, video_url).group(1)
    return filename


def get_courses_from_json(response: str) -> List[str]:
    try:
        json_string = json.loads(response)
        courses = [course["course_path"] for course in json_string["courses"]]
    except ValueError:
        logger.info("Error getting the courses list. Check that you're enrolled on selected courses.")
        courses = []
    return courses


def get_sessions_from_json(response: str, course: str) -> List[Session]:
    sessions = []
    try:
        d = json.loads(response)
        lectures = d["lectures"]
        for lecture in lectures:
            session = Session(course, lecture["order"], slugify(lecture["title"]), lecture["course_session_path"])
            sessions.append(session)
    except Exception as e:
        logger.exception(f"Error while getting session: {e}")
    return sessions


def get_videos_from_json(response: str, resolution: int, session: Session) -> List[Video]:
    parsed_videos = []
    try:
        d = json.loads(response)
        video_format = f"h264_{resolution}_url"
        videos = d["videos"]
        for video in videos:
            v = Video(session, video["order"], video["title"], video[video_format])
            parsed_videos.append(v)
    except Exception as e:
        logger.exception(f"Error getting videos: {e}")
    return parsed_videos


def get_video_title(video_title: str, filename: str) -> str:
    try:
        slug = slugify(video_title)
        video_title = "_".join(filename.split(".")[:-1]) + "p_" + slug + "." + filename.split(".")[-1]
    except IndexError:
        video_title = filename
    return video_title


def write_video(video_url: str, full_path: str, filename: str, chunk_size: int = 4096):
    size = int(requests.head(video_url).headers["Content-Length"])
    size_on_disk = check_if_file_exists(full_path, filename)
    if size_on_disk < size:
        fd = Path(full_path)
        fd.mkdir(parents=True, exist_ok=True)
        with open(fd / filename, "wb") as f:
            r = requests.get(video_url, stream=True)
            current_size = 0
            for chunk in r.iter_content(chunk_size=chunk_size):
                f.write(chunk)
                current_size += chunk_size
                s = progress(current_size, size, filename)
                print(s, end="", flush=True)
            print(s)
    else:
        logger.info(f"{filename} already downloaded, skipping...")


def check_if_file_exists(full_path: str, filename: str) -> int:
    f = Path(full_path + "/" + filename)
    if f.exists():
        return f.stat().st_size
    else:
        return 0
