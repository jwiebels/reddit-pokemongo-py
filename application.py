import base64
import configparser
import logging
import time
import webbrowser
from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from uuid import uuid4

import requests


class PokemonGoFriendsBot:
	COMMON_API_URI: str = "https://www.reddit.com/api/v1"
	OAUTH_API_URI: str = "https://oauth.reddit.com/api"

	REDIRECT_URI: str = "https://www.reddit.com/r/PokemonGoFriends"
	MAX_API_REQUESTS_PER_MINUTE: int = 60

	def __init__(self, client_id: str, client_secret: str, message: str):
		assert all((
			client_id,
			client_secret,
			message
		))

		self.client_id = str(client_id)
		self.client_secret = str(client_secret)
		self.message = str(message)

		self.token: Optional[Token] = None
		self.last_comment_fullname: Optional[str] = None

	def start(self) -> None:
		self.authorize_application()
		code: str = input(">>> Please enter your application code: ")

		if self.authenticate_session(code=code):
			self.run()

	# For further information see:
	# https://github.com/reddit-archive/reddit/wiki/OAuth2
	def authorize_application(self) -> bool:
		logging.info("Authorizing application...")

		url = f"{self.COMMON_API_URI}/authorize"

		params = {
			"client_id": self.client_id,
			"response_type": "code",
			"state": f"{uuid4()}",
			"redirect_uri": self.REDIRECT_URI,
			"duration": "permanent",
			"scope": "edit submit"
		}

		headers = {
			"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:100.0) Gecko/20100101 Firefox/100.0"
		}

		if (r := requests.get(url=url, params=params, headers=headers)).status_code == 200:
			webbrowser.open(url=r.url, new=2)
			return True

		return False

	def authenticate_session(self, code: Optional[str] = None, is_refresh: bool = False) -> bool:
		logging.info("Initializing session...")

		url = f"{self.COMMON_API_URI}/access_token"

		headers = {
			"Authorization": f"Basic {base64.b64encode(f'{self.client_id}:{self.client_secret}'.encode('ascii')).decode('ascii')}",
			"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:100.0) Gecko/20100101 Firefox/100.0"
		}

		if is_refresh:
			data = {
				"grant_type": "refresh_token",
				"refresh_token": self.token.refresh_token
			}
		else:
			data = {
				"grant_type": "authorization_code",
				"code": code,
				"redirect_uri": self.REDIRECT_URI
			}

		if (r := requests.post(url=url, headers=headers, data=data)).status_code == 200:
			try:
				r_json = r.json()
			except Exception:
				logging.debug("Could not load access token...")
				return False

			if is_refresh:
				self.token.refresh(response=r_json)
				print("> Successfully refreshed authentication token.")
			else:
				self.token = Token(
					access_token=r_json['access_token'],
					expires_in=int(r_json['expires_in']),
					scope=r_json['scope'],
					refresh_token=r_json['refresh_token'])
				print("> Successfully obtained authentication token.")

			return True

		return False

	def run(self) -> None:
		logging.info("Running...")

		while True:
			if not self.post_comment():
				break

			time.sleep(60 * 15 * 1)
			if self.last_comment_fullname:
				if not self.delete_comment():
					break

				time.sleep(15 * 1 * 1)

	def post_comment(self):
		self.check_token_expiration()

		logging.info("Posting comment...")

		url = f"{self.OAUTH_API_URI}/comment"

		data = {
			"api_type": "json",
			"return_rtjson": True,
			"text": self.message,
			"thing_id": "t3_so87rb"  # Thread fullname: t3_so87rb
		}

		headers = {
			"Authorization": f"{self.token}",
			"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:100.0) Gecko/20100101 Firefox/100.0",
		}

		if (r := requests.post(url=url, headers=headers, data=data)).status_code == 200:
			try:
				r_json = r.json()
			except Exception:
				logging.debug("Could not load access token...")
				return False

			self.last_comment_fullname = r_json['name']

			print("> Successfully posted comment.")
			return True

		logging.error("[!] Unable to post new comment. Exiting...")
		return False

	def delete_comment(self):
		self.check_token_expiration()

		logging.info("Deleting previous comment...")

		url = f"{self.OAUTH_API_URI}/del"

		data = {
			"id": self.last_comment_fullname
		}

		headers = {
			"Authorization": f"{self.token}",
			"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:100.0) Gecko/20100101 Firefox/100.0",
		}

		if requests.post(url=url, headers=headers, data=data).status_code == 200:
			print("> Successfully deleted last comment.")
			return True

		logging.error("[!] Unable to delete latest comment. Exiting...")
		return False

	def check_token_expiration(self):
		if not self.token.is_expired:
			return
		else:
			self.authenticate_session(is_refresh=True)


@dataclass
class Token:
	access_token: str
	expires_in: int
	scope: str

	refresh_token: str

	token_type: str = "bearer"
	issued_at: datetime = datetime.now()

	def __str__(self) -> str:
		return f"{self.token_type} {self.access_token}"

	@property
	def is_expired(self) -> bool:
		return (datetime.now() - self.issued_at).total_seconds() >= self.expires_in - 60

	def refresh(self, response: dict):
		self.access_token = response['access_token']
		self.expires_in = response['expires_in']
		self.scope = response['scope']

		self.issued_at = datetime.now()


if __name__ == "__main__":
	parser = configparser.RawConfigParser()
	parser.read("./config.cfg")

	config = dict(parser.items('CONFIG'))

	bot = PokemonGoFriendsBot(**config)
	bot.start()
