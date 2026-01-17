import sys

from bs4 import BeautifulSoup


def extract_transcript(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    soup = BeautifulSoup(content, 'html.parser')

    # Find all yt-formatted-string elements with segment-text class
    segments = soup.find_all('yt-formatted-string', class_='segment-text')

    # Extract text and join
    transcript = ' '.join(segment.get_text(strip=True) for segment in segments)

    return transcript


if __name__ == '__main__':
    file_path = sys.argv[1]

    transcript = extract_transcript(file_path)
    print(transcript)
