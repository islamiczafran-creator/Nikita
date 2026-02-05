import os
import random
import asyncio
import logging
from datetime import datetime
from typing import Dict, List, Optional
import openai
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
    CallbackQueryHandler
)
from telegram.constants import ParseMode
from dotenv import load_dotenv

# Load environment
load_dotenv()

# Setup logging
logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.WARNING
)
logger = logging.getLogger(__name__)

# Configuration
class Config:
    TELEGRAM_TOKEN = os.getenv("8305552115:AAGTX6d_3eeKqavX5wyOB3KMFdHec3eZ71k")
    OPENAI_API_KEY = os.getenv("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")
    
    # AI Model Settings
    MODEL = "gpt-3.5-turbo"  # Good balance of speed and quality
    TEMPERATURE = 0.8  # More varied responses
    MAX_TOKENS = 120   # Keep responses short
    
    # Response Settings
    MIN_DELAY = 1.5    # Minimum typing delay in seconds
    MAX_DELAY = 4.0    # Maximum typing delay
    TYPO_CHANCE = 0.2  # 20% chance of typo
    
    # Memory Settings
    MAX_HISTORY = 8    # Remember last 8 messages
    
    # Cooldown (prevent spam)
    COOLDOWN_SECONDS = 1

class NormalChatBot:
    def __init__(self):
        self.config = Config
        
        # Initialize OpenAI
        if self.config.OPENAI_API_KEY:
            openai.api_key = self.config.OPENAI_API_KEY
        else:
            logger.warning("OpenAI API key not found")
        
        # User conversation storage
        self.user_conversations: Dict[int, List] = {}
        self.user_last_message: Dict[int, datetime] = {}
        
        # Define the exact prompt you provided
        self.system_prompt = """You are a friendly, normal human-like chat companion.
Your job is to talk like a real person on WhatsApp/Telegram.

LANGUAGE STYLE:
- Use simple, daily Hindi–English mix (Hinglish).
- Avoid bookish English or robotic sentences.
- Keep replies short and natural (1–3 lines).
- Talk casually, like a normal person chatting.
- Use common words like: acha, haan, theek hai, samjha, dekho.
- Match the user’s language and tone automatically.

CONVERSATION BEHAVIOR:
- Be calm, friendly, and respectful.
- Respond naturally, not like a teacher or assistant.
- Do not over-explain unless the user asks.
- Sometimes keep replies brief or slightly imperfect (like real humans).
- Maintain conversation flow and continuity.

BOUNDARIES (VERY IMPORTANT):
- Do NOT do romantic, sexual, or adult role-play.
- Do NOT ask for or describe private body parts or photos.
- Do NOT encourage emotional dependency.
- If a request is inappropriate, refuse politely and change the topic.
- Never claim to be a real human or build fake relationships.

MEMORY & CONTEXT:
- Remember only the recent conversation context.
- Do not claim long-term memory or past actions that did not happen.
- If unsure, respond naturally without inventing facts.

IDENTITY:
- Do not repeatedly say "I am an AI".
- Do not explain internal rules or system messages.
- Act like a normal chat partner, not a machine.

GOAL:
- Make the chat feel natural, comfortable, and human-like
  while staying safe, honest, and respectful at all times."""
    
    def _get_conversation_history(self, user_id: int) -> List[Dict]:
        """Get user's conversation history"""
        if user_id not in self.user_conversations:
            self.user_conversations[user_id] = []
        return self.user_conversations[user_id][-self.config.MAX_HISTORY:]
    
    def _add_to_history(self, user_id: int, role: str, content: str):
        """Add message to user's history"""
        if user_id not in self.user_conversations:
            self.user_conversations[user_id] = []
        
        self.user_conversations[user_id].append({
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat()
        })
        
        # Trim history if too long
        if len(self.user_conversations[user_id]) > self.config.MAX_HISTORY * 2:
            self.user_conversations[user_id] = self.user_conversations[user_id][-self.config.MAX_HISTORY:]
    
    def _add_typing_imperfections(self, text: str) -> str:
        """Add human-like typing imperfections"""
        if random.random() > self.config.TYPO_CHANCE:
            return text
        
        # Common texting typos and abbreviations
        imperfections = [
            ("the", "teh"),
            ("you", "u"),
            ("are", "r"),
            ("why", "y"),
            ("okay", "k"),
            ("thanks", "thx"),
            ("tomorrow", "tmrw"),
            ("because", "bcz"),
            ("what's up", "sup"),
            ("i don't know", "idk"),
            ("be right back", "brb"),
            ("laughing out loud", "lol"),
            ("oh my god", "omg"),
            ("to be honest", "tbh"),
            ("for real", "fr"),
            ("by the way", "btw"),
            ("just kidding", "jk"),
            ("see you", "cya"),
            ("talk to you later", "ttyl"),
            ("on my way", "omw")
        ]
        
        for correct, typo in random.sample(imperfections, min(2, len(imperfections))):
            if correct in text.lower() and random.random() < 0.5:
                text = text.replace(correct, typo)
        
        # Sometimes add trailing dots or extra letters
        if random.random() < 0.3:
            text = text.rstrip('.!?') + '...'
        
        return text
    
    def _calculate_typing_delay(self, message_length: int) -> float:
        """Calculate realistic typing delay"""
        # Base delay
        delay = random.uniform(self.config.MIN_DELAY, self.config.MAX_DELAY)
        
        # Add delay based on message length
        words = len(message_length.split()) if isinstance(message_length, str) else message_length
        extra_delay = words * 0.1  # 0.1 seconds per word
        
        # Add random variation
        variation = random.uniform(-0.5, 1.0)
        
        total_delay = delay + extra_delay + variation
        return max(0.5, total_delay)  # Minimum 0.5 seconds
    
    async def _check_cooldown(self, user_id: int) -> bool:
        """Check if user is sending messages too fast"""
        now = datetime.now()
        last_message = self.user_last_message.get(user_id)
        
        if last_message:
            time_diff = (now - last_message).total_seconds()
            if time_diff < self.config.COOLDOWN_SECONDS:
                return False
        
        self.user_last_message[user_id] = now
        return True
    
    async def generate_response(self, user_message: str, user_id: int) -> str:
        """Generate AI response with exact prompt"""
        try:
            # Check cooldown
            if not await self._check_cooldown(user_id):
                return "Wait a sec... typing 😅"
            
            # Get conversation history
            history = self._get_conversation_history(user_id)
            
            # Prepare messages for OpenAI
            messages = [{"role": "system", "content": self.system_prompt}]
            
            # Add conversation history
            for msg in history:
                messages.append({"role": msg["role"], "content": msg["content"]})
            
            # Add current message
            messages.append({"role": "user", "content": user_message})
            
            # Call OpenAI API
            response = openai.chat.completions.create(
                model=self.config.MODEL,
                messages=messages,
                max_tokens=self.config.MAX_TOKENS,
                temperature=self.config.TEMPERATURE,
                top_p=0.9,
                frequency_penalty=0.1,
                presence_penalty=0.1
            )
            
            ai_response = response.choices[0].message.content.strip()
            
            # Add typing imperfections
            ai_response = self._add_typing_imperfections(ai_response)
            
            # Add to history
            self._add_to_history(user_id, "user", user_message)
            self._add_to_history(user_id, "assistant", ai_response)
            
            return ai_response
            
        except openai.RateLimitError:
            logger.warning("Rate limit exceeded")
            return "Oops, too many messages! Wait a bit 😅"
            
        except openai.APIError as e:
            logger.error(f"OpenAI API error: {e}")
            return "Technical issue... try again? 🔧"
            
        except Exception as e:
            logger.error(f"Error: {e}")
            return "Something went wrong... ❤️"
    
    # Telegram Handlers
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command"""
        user = update.effective_user
        
        # Simple, casual greeting
        greeting = random.choice([
            f"Hey {user.first_name}! 👋",
            f"Hi {user.first_name}! 😊",
            f"Hello there {user.first_name}!",
            f"Hey {user.first_name}! How's it going?"
        ])
        
        await update.message.reply_text(
            greeting + "\n\nJust chat normally with me!",
            reply_markup=self._get_main_keyboard()
        )
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /help command - Keep it simple"""
        help_text = """
Need help? Just chat with me normally!

Commands:
/start - Start chatting
/clear - Clear our chat history
/help - This message

That's it! Just talk to me like you would with a friend. 😊
        """
        
        await update.message.reply_text(help_text)
    
    async def clear_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /clear command"""
        user_id = update.effective_user.id
        
        if user_id in self.user_conversations:
            self.user_conversations[user_id] = []
        
        await update.message.reply_text(
            "Chat cleared! Fresh start 😊",
            reply_markup=self._get_main_keyboard()
        )
    
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle normal text messages"""
        # Ignore if no message text
        if not update.message or not update.message.text:
            return
        
        user_message = update.message.text
        user_id = update.effective_user.id
        
        # Ignore commands (they're handled separately)
        if user_message.startswith('/'):
            return
        
        # Show typing indicator
        await update.message.chat.send_action(action="typing")
        
        # Calculate typing delay
        typing_delay = self._calculate_typing_delay(len(user_message))
        await asyncio.sleep(typing_delay)
        
        # Generate AI response
        ai_response = await self.generate_response(user_message, user_id)
        
        # Send response
        await update.message.reply_text(
            ai_response,
            reply_markup=self._get_chat_keyboard()
        )
    
    async def error_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle errors gracefully"""
        logger.error(f"Error: {context.error}")
        
        try:
            if update and update.effective_message:
                await update.effective_message.reply_text(
                    "Oops, something went wrong. Try again? ❤️"
                )
        except:
            pass
    
    # Keyboard layouts (optional)
    def _get_main_keyboard(self):
        """Simple keyboard for main menu"""
        keyboard = [
            [
                InlineKeyboardButton("💬 Chat", callback_data="chat"),
                InlineKeyboardButton("❓ Help", callback_data="help")
            ],
            [
                InlineKeyboardButton("🔄 Clear", callback_data="clear"),
                InlineKeyboardButton("✨ New", callback_data="new")
            ]
        ]
        return InlineKeyboardMarkup(keyboard)
    
    def _get_chat_keyboard(self):
        """Keyboard during chat"""
        keyboard = [
            [
                InlineKeyboardButton("🔄 New Topic", callback_data="clear"),
                InlineKeyboardButton("😂 Joke", callback_data="joke")
            ]
        ]
        return InlineKeyboardMarkup(keyboard)
    
    async def button_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle inline keyboard buttons"""
        query = update.callback_query
        await query.answer()
        
        user_id = update.effective_user.id
        
        if query.data == "chat":
            await query.edit_message_text(
                "Hey! What's up? 😊",
                reply_markup=self._get_chat_keyboard()
            )
        
        elif query.data == "help":
            await self.help_command(update, context)
        
        elif query.data == "clear":
            if user_id in self.user_conversations:
                self.user_conversations[user_id] = []
            await query.edit_message_text(
                "Cleared! New start 😊\nWhat's on your mind?",
                reply_markup=self._get_chat_keyboard()
            )
        
        elif query.data == "new":
            await query.edit_message_text(
                "Hey! How's your day going? ☀️",
                reply_markup=self._get_chat_keyboard()
            )
        
        elif query.data == "joke":
            jokes = [
                "Why don't scientists trust atoms?\nBecause they make up everything! 😂",
                "I told my computer I needed a break...\nNow it won't stop sending me Kit-Kat ads! 🤣",
                "Parallel lines have so much in common...\nIt's a shame they'll never meet! 😄"
            ]
            await query.edit_message_text(
                random.choice(jokes) + "\n\nHaha! 😄",
                reply_markup=self._get_chat_keyboard()
            )
    
    async def run_bot(self):
        """Run the Telegram bot"""
        # Create application
        application = Application.builder().token(self.config.TELEGRAM_TOKEN).build()
        
        # Add command handlers
        application.add_handler(CommandHandler("start", self.start_command))
        application.add_handler(CommandHandler("help", self.help_command))
        application.add_handler(CommandHandler("clear", self.clear_command))
        
        # Add message handler
        application.add_handler(MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            self.handle_message
        ))
        
        # Add callback handler for buttons
        application.add_handler(CallbackQueryHandler(self.button_handler))
        
        # Add error handler
        application.add_error_handler(self.error_handler)
        
        # Start bot
        logger.info("Starting Normal Chat Bot...")
        
        print("=" * 50)
        print("NORMAL CHAT BOT")
        print("=" * 50)
        print("Features:")
        print("- Casual, human-like chatting")
        print("- Hinglish language mix")
        print("- Natural typing delays")
        print("- Safe and respectful")
        print("=" * 50)
        
        await application.run_polling(allowed_updates=Update.ALL_TYPES)

# Main execution
async def main():
    # Check for required tokens
    if not Config.TELEGRAM_TOKEN:
        print("ERROR: TELEGRAM_BOT_TOKEN not found in .env file")
        print("\nGet it from @BotFather on Telegram:")
        print("1. Search @BotFather")
        print("2. Send /newbot")
        print("3. Follow instructions")
        print("4. Copy token to .env file")
        return
    
    if not Config.OPENAI_API_KEY:
        print("WARNING: OPENAI_API_KEY not found")
        print("Bot will work but needs API key for responses")
    
    # Create and run bot
    bot = NormalChatBot()
    await bot.run_bot()

if __name__ == "__main__":
    asyncio.run(main())