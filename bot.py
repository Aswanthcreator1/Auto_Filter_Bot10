import logging
import logging.config

# Get logging configurations
logging.config.fileConfig('logging.conf')
logging.getLogger().setLevel(logging.INFO)
logging.getLogger("pyrogram").setLevel(logging.ERROR)
logging.getLogger("imdbpy").setLevel(logging.ERROR)


from pyrogram import Client, __version__, filters
from pyrogram.raw.all import layer
from database.ia_filterdb import Media
from database.users_chats_db import db
from info import SESSION, API_ID, API_HASH, BOT_TOKEN, LOG_STR, LOG_CHANNEL, PORT
from utils import temp
from typing import Union, Optional, AsyncGenerator
from pyrogram import types
from Script import script
from datetime import date, datetime
import pytz
from aiohttp import web
from plugins import web_server


class Bot(Client):

    def __init__(self):
        super().__init__(
            name=SESSION,
            api_id=API_ID,
            api_hash=API_HASH,
            bot_token=BOT_TOKEN,
            workers=50,
            plugins={"root": "plugins"},
            sleep_threshold=5,
        )

    async def start(self):
        # Load banned lists into temp
        b_users, b_chats = await db.get_banned()
        temp.BANNED_USERS = b_users
        temp.BANNED_CHATS = b_chats

        # Start pyrogram client
        await super().start()

        # Ensure DB indexes
        await Media.ensure_indexes()

        # Cache bot info
        me = await self.get_me()
        temp.ME = me.id
        temp.U_NAME = me.username
        temp.B_NAME = me.first_name
        self.username = '@' + me.username

        logging.info(f"{me.first_name} with for Pyrogram v{__version__} (Layer {layer}) started on {me.username}.")
        logging.info(LOG_STR)

        # Prepare timestamp
        tz = pytz.timezone('Asia/Kolkata')
        today = date.today()
        now = datetime.now(tz)
        time = now.strftime("%H:%M:%S %p")

        # ----------------------------------------- #
        # FIX: Load LOG_CHANNEL peer before sending
        # This prevents "Peer id invalid" on fresh sessions
        # ----------------------------------------- #
        try:
            await self.get_chat(LOG_CHANNEL)
        except Exception as e:
            logging.error(f"LOG_CHANNEL load error: {e}")

        # ----------------------------------------- #
        # FIX: Safe send_message so bot doesn't crash
        # ----------------------------------------- #
        try:
            await self.send_message(
                chat_id=LOG_CHANNEL,
                text=script.RESTART_TXT.format(today, time)
            )
        except Exception as e:
            logging.error(f"Failed to send LOG message: {e}")
        # ----------------------------------------- #

        # Start webserver for plugins
        app = web.AppRunner(await web_server())
        await app.setup()
        bind_address = "0.0.0.0"
        await web.TCPSite(app, bind_address, PORT).start()

    async def stop(self, *args):
        # Called on shutdown
        await super().stop()
        logging.info("Bot stopped. Bye.")

    async def iter_messages(
        self,
        chat_id: Union[int, str],
        limit: int,
        offset: int = 0,
    ) -> Optional[AsyncGenerator["types.Message", None]]:
        """
        Iterate through a chat sequentially.
        This convenience method does the same as repeatedly calling Client.get_messages
        in a loop. Useful for paging large chats.

        Parameters:
            chat_id (int | str): chat id or username
            limit (int): number of messages to iterate
            offset (int): start offset (default 0)

        Yields:
            pyrogram.types.Message objects
        """
        current = offset
        while True:
            new_diff = min(200, limit - current)
            if new_diff <= 0:
                return
            # request message IDs from current to current+new_diff (inclusive)
            messages = await self.get_messages(chat_id, list(range(current, current + new_diff + 1)))
            for message in messages:
                yield message
                current += 1


if __name__ == "__main__":
    app = Bot()
    app.run()
