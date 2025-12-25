import logging
import os
from typing import Dict, List, Optional, Tuple
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ChatMember, User
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
    CallbackQueryHandler
)
from telegram.constants import ParseMode
from datetime import datetime, timedelta
from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId
import asyncio
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# MongoDB Configuration
MONGO_URI = os.getenv("MONGO_URI", "mongodb+srv://Fugui:tianlu@cluster0.6hyrp0r.mongodb.net/?appName=Cluster0")
DB_NAME = "telegram_filter_bot"

class MongoDB:
    def __init__(self):
        self.client = None
        self.db = None
        
    async def connect(self):
        """Connect to MongoDB"""
        try:
            self.client = AsyncIOMotorClient(MONGO_URI)
            self.db = self.client[DB_NAME]
            
            # Create indexes
            await self.db.filters.create_index([("chat_id", 1), ("keyword", 1)], unique=True)
            await self.db.connections.create_index([("user_id", 1)], unique=True)
            await self.db.channels.create_index([("channel_id", 1)], unique=True)
            await self.db.admins.create_index([("user_id", 1), ("chat_id", 1)], unique=True)
            await self.db.stats.create_index([("date", 1)], unique=True)
            
            logger.info("Connected to MongoDB successfully")
        except Exception as e:
            logger.error(f"Failed to connect to MongoDB: {e}")
            raise
    
    async def add_filter(self, chat_id: int, keyword: str, response: str, created_by: int) -> bool:
        """Add a new filter"""
        try:
            filter_data = {
                "chat_id": chat_id,
                "keyword": keyword.lower(),
                "response": response,
                "created_by": created_by,
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            }
            await self.db.filters.update_one(
                {"chat_id": chat_id, "keyword": keyword.lower()},
                {"$set": filter_data},
                upsert=True
            )
            return True
        except Exception as e:
            logger.error(f"Error adding filter: {e}")
            return False
    
    async def delete_filter(self, chat_id: int, keyword: str) -> bool:
        """Delete a filter"""
        try:
            result = await self.db.filters.delete_one({
                "chat_id": chat_id,
                "keyword": keyword.lower()
            })
            return result.deleted_count > 0
        except Exception as e:
            logger.error(f"Error deleting filter: {e}")
            return False
    
    async def get_filters(self, chat_id: int) -> List[Dict]:
        """Get all filters for a chat"""
        try:
            cursor = self.db.filters.find({"chat_id": chat_id}).sort("keyword", 1)
            filters_list = await cursor.to_list(length=1000)
            return filters_list
        except Exception as e:
            logger.error(f"Error getting filters: {e}")
            return []
    
    async def get_filter(self, chat_id: int, keyword: str) -> Optional[Dict]:
        """Get a specific filter"""
        try:
            return await self.db.filters.find_one({
                "chat_id": chat_id,
                "keyword": keyword.lower()
            })
        except Exception as e:
            logger.error(f"Error getting filter: {e}")
            return None
    
    async def add_connection(self, user_id: int, group_id: int) -> bool:
        """Add connection between user and group"""
        try:
            connection_data = {
                "user_id": user_id,
                "group_id": group_id,
                "connected_at": datetime.utcnow()
            }
            await self.db.connections.update_one(
                {"user_id": user_id},
                {"$set": connection_data},
                upsert=True
            )
            return True
        except Exception as e:
            logger.error(f"Error adding connection: {e}")
            return False
    
    async def get_connection(self, user_id: int) -> Optional[Dict]:
        """Get user's connection"""
        try:
            return await self.db.connections.find_one({"user_id": user_id})
        except Exception as e:
            logger.error(f"Error getting connection: {e}")
            return None
    
    async def delete_connection(self, user_id: int) -> bool:
        """Delete user's connection"""
        try:
            result = await self.db.connections.delete_one({"user_id": user_id})
            return result.deleted_count > 0
        except Exception as e:
            logger.error(f"Error deleting connection: {e}")
            return False
    
    async def add_channel(self, channel_id: int, title: str, added_by: int) -> bool:
        """Add a channel to database"""
        try:
            channel_data = {
                "channel_id": channel_id,
                "title": title,
                "added_by": added_by,
                "added_at": datetime.utcnow(),
                "is_active": True
            }
            await self.db.channels.update_one(
                {"channel_id": channel_id},
                {"$set": channel_data},
                upsert=True
            )
            return True
        except Exception as e:
            logger.error(f"Error adding channel: {e}")
            return False
    
    async def get_channels(self, skip: int = 0, limit: int = 50) -> Tuple[List[Dict], int]:
        """Get all channels with pagination"""
        try:
            total = await self.db.channels.count_documents({"is_active": True})
            cursor = self.db.channels.find({"is_active": True}).skip(skip).limit(limit)
            channels = await cursor.to_list(length=limit)
            return channels, total
        except Exception as e:
            logger.error(f"Error getting channels: {e}")
            return [], 0
    
    async def get_channel(self, channel_id: int) -> Optional[Dict]:
        """Get specific channel"""
        try:
            return await self.db.channels.find_one({"channel_id": channel_id})
        except Exception as e:
            logger.error(f"Error getting channel: {e}")
            return None
    
    async def delete_channel(self, channel_id: int) -> bool:
        """Delete channel from database"""
        try:
            result = await self.db.channels.delete_one({"channel_id": channel_id})
            return result.deleted_count > 0
        except Exception as e:
            logger.error(f"Error deleting channel: {e}")
            return False
    
    async def add_admin(self, chat_id: int, user_id: int, added_by: int) -> bool:
        """Add admin to database"""
        try:
            admin_data = {
                "chat_id": chat_id,
                "user_id": user_id,
                "added_by": added_by,
                "added_at": datetime.utcnow()
            }
            await self.db.admins.update_one(
                {"chat_id": chat_id, "user_id": user_id},
                {"$set": admin_data},
                upsert=True
            )
            return True
        except Exception as e:
            logger.error(f"Error adding admin: {e}")
            return False
    
    async def is_admin(self, chat_id: int, user_id: int) -> bool:
        """Check if user is admin in database"""
        try:
            admin = await self.db.admins.find_one({
                "chat_id": chat_id,
                "user_id": user_id
            })
            return admin is not None
        except Exception as e:
            logger.error(f"Error checking admin: {e}")
            return False
    
    async def remove_admin(self, chat_id: int, user_id: int) -> bool:
        """Remove admin from database"""
        try:
            result = await self.db.admins.delete_one({
                "chat_id": chat_id,
                "user_id": user_id
            })
            return result.deleted_count > 0
        except Exception as e:
            logger.error(f"Error removing admin: {e}")
            return False
    
    async def log_stats(self, command: str, user_id: int, chat_id: int):
        """Log command usage statistics"""
        try:
            today = datetime.utcnow().date()
            await self.db.stats.update_one(
                {"date": today},
                {
                    "$inc": {f"commands.{command}": 1, "total": 1},
                    "$addToSet": {"users": user_id, "chats": chat_id}
                },
                upsert=True
            )
        except Exception as e:
            logger.error(f"Error logging stats: {e}")
    
    async def get_stats(self, days: int = 7) -> Dict:
        """Get statistics for last N days"""
        try:
            start_date = datetime.utcnow() - timedelta(days=days)
            pipeline = [
                {"$match": {"date": {"$gte": start_date}}},
                {"$group": {
                    "_id": None,
                    "total_commands": {"$sum": "$total"},
                    "unique_users": {"$sum": {"$size": "$users"}},
                    "unique_chats": {"$sum": {"$size": "$chats"}},
                    "command_breakdown": {"$push": "$commands"}
                }}
            ]
            result = await self.db.stats.aggregate(pipeline).to_list(length=1)
            return result[0] if result else {}
        except Exception as e:
            logger.error(f"Error getting stats: {e}")
            return {}

class FilterBot:
    def __init__(self, token: str):
        self.token = token
        self.db = MongoDB()
        
    async def initialize(self):
        """Initialize database connection"""
        await self.db.connect()
    
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Send welcome message"""
        user = update.effective_user
        
        # Log stats
        await self.db.log_stats("start", user.id, update.effective_chat.id)
        
        welcome_text = f"""👋 𝖧𝖾𝗅𝗅𝗈 {user.mention_html()}!

🤖 *𝖥𝗂𝗅𝗍𝖾𝗋 𝖡𝗈𝗍 𝖶𝗂𝗍𝗁 𝖬𝗈𝗇𝗀𝗈𝖣𝖡 & 𝖢𝗁𝖺𝗇𝗇𝖾𝗅 𝖲𝗎𝗉𝗉𝗈𝗋𝗍*

*𝖥𝗂𝗅𝗍𝖾𝗋 𝖢𝗈𝗆𝗆𝖺𝗇𝖽𝗌:*
• /add <keyword> <response> - 𝖲𝖾𝗍 𝖺𝗎𝗍𝗈-𝗋𝖾𝗉𝗅𝗒 𝖿𝗈𝗋 𝗄𝖾𝗒𝗐𝗈𝗋𝖽
• /del <keyword> - 𝖱𝖾𝗆𝗈𝗏𝖾 𝖿𝗂𝗅𝗍𝖾𝗋
• /filters - 𝖫𝗂𝗌𝗍 𝖺𝗅𝗅 𝖿𝗂𝗅𝗍𝖾𝗋𝗌

*𝖢𝗈𝗇𝗇𝖾𝖼𝗍𝗂𝗈𝗇 𝖢𝗈𝗆𝗆𝖺𝗇𝖽𝗌:*
• /connect <group_id> - 𝖫𝗂𝗇𝗄 𝗀𝗋𝗈𝗎𝗉 𝗍𝗈 𝖯𝖬
• /connections - 𝖲𝗁𝗈𝗐 𝗅𝗂𝗇𝗄𝖾𝖽 𝗀𝗋𝗈𝗎𝗉𝗌
• /disconnect - 𝖱𝖾𝗆𝗈𝗏𝖾 𝖼𝗈𝗇𝗇𝖾𝖼𝗍𝗂𝗈𝗇

*𝖢𝗁𝖺𝗇𝗇𝖾𝗅 𝖣𝖺𝗍𝖺𝖻𝖺𝗌𝖾 𝖢𝗈𝗆𝗆𝖺𝗇𝖽𝗌:*
• /addchannel - 𝖠𝖽𝖽 𝖼𝗁𝖺𝗇𝗇𝖾𝗅 𝗍𝗈 𝖽𝖺𝗍𝖺𝖻𝖺𝗌𝖾
• /channels - 𝖫𝗂𝗌𝗍 𝖺𝗅𝗅 𝖼𝗁𝖺𝗇𝗇𝖾𝗅𝗌
• /delchannel <id> - 𝖱𝖾𝗆𝗈𝗏𝖾 𝖼𝗁𝖺𝗇𝗇𝖾𝗅

*𝖠𝖽𝗆𝗂𝗇 𝖢𝗈𝗆𝗆𝖺𝗇𝖽𝗌:*
• /addadmin <user_id> - 𝖠𝖽𝖽 𝖺𝖽𝗆𝗂𝗇
• /removeadmin <user_id> - 𝖱𝖾𝗆𝗈𝗏𝖾 𝖺𝖽𝗆𝗂𝗇
• /admins - 𝖲𝗁𝗈𝗐 𝖺𝖽𝗆𝗂𝗇𝗌
• /stats - 𝖡𝗈𝗍 𝗌𝗍𝖺𝗍𝗂𝗌𝗍𝗂𝖼𝗌

*𝖮𝗍𝗁𝖾𝗋 𝖢𝗈𝗆𝗆𝖺𝗇𝖽𝗌:*
• /id - 𝖦𝖾𝗍 𝗎𝗌𝖾𝗋/𝗀𝗋𝗈𝗎𝗉 𝖨𝖣
• /info <user_id> - 𝖦𝖾𝗍 𝗎𝗌𝖾𝗋 𝖽𝖾𝗍𝖺𝗂𝗅𝗌

*𝖲𝗎𝗉𝗉𝗈𝗋𝗍:* @Rare_Anime_Chat_Group
"""
        await update.message.reply_html(welcome_text, parse_mode=ParseMode.MARKDOWN)
    
    async def add_filter(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Add a new filter"""
        chat_id = update.effective_chat.id
        user_id = update.effective_user.id
        
        # Log stats
        await self.db.log_stats("add_filter", user_id, chat_id)
        
        # Check admin permissions
        if update.effective_chat.type in ['group', 'supergroup']:
            is_admin = await self.db.is_admin(chat_id, user_id)
            if not is_admin:
                # Check Telegram admin status
                try:
                    user = await update.effective_chat.get_member(user_id)
                    if user.status not in [ChatMember.ADMINISTRATOR, ChatMember.OWNER]:
                        await update.message.reply_text("❌ 𝖸𝗈𝗎 𝗇𝖾𝖾𝖽 𝖺𝖽𝗆𝗂𝗇 𝗋𝗂𝗀𝗁𝗍𝗌 𝗍𝗈 𝖺𝖽𝖽 𝖿𝗂𝗅𝗍𝖾𝗋𝗌!")
                        return
                except:
                    await update.message.reply_text("❌ 𝖸𝗈𝗎 𝗇𝖾𝖾𝖽 𝖺𝖽𝗆𝗂𝗇 𝗋𝗂𝗀𝗁𝗍𝗌 𝗍𝗈 𝖺𝖽𝖽 𝖿𝗂𝗅𝗍𝖾𝗋𝗌!")
                    return
        
        if not context.args or len(context.args) < 2:
            await update.message.reply_text("❌ 𝖴𝗌𝖺𝗀𝖾: /add keyword response")
            return
        
        keyword = context.args[0].lower()
        response = ' '.join(context.args[1:])
        
        # Check if filter already exists
        existing = await self.db.get_filter(chat_id, keyword)
        if existing:
            await update.message.reply_text(f"⚠️ 𝖥𝗂𝗅𝗍𝖾𝗋 𝖿𝗈𝗋 '{keyword}' 𝖺𝗅𝗋𝖾𝖺𝖽𝗒 𝖾𝗑𝗂𝗌𝗍𝗌!")
            return
        
        # Add filter to database
        success = await self.db.add_filter(chat_id, keyword, response, user_id)
        
        if success:
            await update.message.reply_text(f"✅ 𝖥𝗂𝗅𝗍𝖾𝗋 𝖺𝖽𝖽𝖾𝖽 𝖿𝗈𝗋 '{keyword}'")
        else:
            await update.message.reply_text("❌ 𝖥𝖺𝗂𝗅𝖾𝖽 𝗍𝗈 𝖺𝖽𝖽 𝖿𝗂𝗅𝗍𝖾𝗋. 𝖯𝗅𝖾𝖺𝗌𝖾 𝗍𝗋𝗒 𝖺𝗀𝖺𝗂𝗇.")
    
    async def delete_filter(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Delete a filter"""
        chat_id = update.effective_chat.id
        user_id = update.effective_user.id
        
        # Log stats
        await self.db.log_stats("delete_filter", user_id, chat_id)
        
        # Check admin permissions
        if update.effective_chat.type in ['group', 'supergroup']:
            is_admin = await self.db.is_admin(chat_id, user_id)
            if not is_admin:
                try:
                    user = await update.effective_chat.get_member(user_id)
                    if user.status not in [ChatMember.ADMINISTRATOR, ChatMember.OWNER]:
                        await update.message.reply_text("❌ 𝖸𝗈𝗎 𝗇𝖾𝖾𝖽 𝖺𝖽𝗆𝗂𝗇 𝗋𝗂𝗀𝗁𝗍𝗌 𝗍𝗈 𝖽𝖾𝗅𝖾𝗍𝖾 𝖿𝗂𝗅𝗍𝖾𝗋𝗌!")
                        return
                except:
                    await update.message.reply_text("❌ 𝖸𝗈𝗎 𝗇𝖾𝖾𝖽 𝖺𝖽𝗆𝗂𝗇 𝗋𝗂𝗀𝗁𝗍𝗌 𝗍𝗈 𝖽𝖾𝗅𝖾𝗍𝖾 𝖿𝗂𝗅𝗍𝖾𝗋𝗌!")
                    return
        
        if not context.args:
            await update.message.reply_text("❌ 𝖴𝗌𝖺𝗀𝖾: /del keyword")
            return
        
        keyword = context.args[0].lower()
        
        # Delete filter from database
        success = await self.db.delete_filter(chat_id, keyword)
        
        if success:
            await update.message.reply_text(f"✅ 𝖥𝗂𝗅𝗍𝖾𝗋 𝖽𝖾𝗅𝖾𝗍𝖾𝖽 𝖿𝗈𝗋 '{keyword}'")
        else:
            await update.message.reply_text(f"❌ 𝖭𝗈 𝖿𝗂𝗅𝗍𝖾𝗋 𝖿𝗈𝗎𝗇𝖽 𝖿𝗈𝗋 '{keyword}'")
    
    async def list_filters(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """List all filters"""
        chat_id = update.effective_chat.id
        
        # Log stats
        await self.db.log_stats("list_filters", update.effective_user.id, chat_id)
        
        filters_list = await self.db.get_filters(chat_id)
        
        if not filters_list:
            await update.message.reply_text("📭 𝖭𝗈 𝖿𝗂𝗅𝗍𝖾𝗋𝗌 𝖺𝖽𝖽𝖾𝖽 𝗒𝖾𝗍!")
            return
        
        filters_text = "🔍 *𝖠𝖼𝗍𝗂𝗏𝖾 𝖥𝗂𝗅𝗍𝖾𝗋𝗌:*\n\n"
        for i, filter_data in enumerate(filters_list, 1):
            keyword = filter_data['keyword']
            response_preview = filter_data['response'][:30] + "..." if len(filter_data['response']) > 30 else filter_data['response']
            filters_text += f"*{i}.* `{keyword}` → {response_preview}\n"
        
        # Add pagination if too many filters
        if len(filters_text) > 4000:
            filters_text = filters_text[:4000] + "\n\n... 𝖺𝗇𝖽 𝗆𝗈𝗋𝖾"
        
        await update.message.reply_text(filters_text, parse_mode=ParseMode.MARKDOWN)
    
    async def connect_group(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Connect a group to PM"""
        user_id = update.effective_user.id
        
        # Log stats
        await self.db.log_stats("connect_group", user_id, update.effective_chat.id)
        
        if not context.args:
            await update.message.reply_text(
                "❌ 𝖴𝗌𝖺𝗀𝖾: /connect group_id\n"
                "𝖦𝖾𝗍 𝗀𝗋𝗈𝗎𝗉 𝖨𝖣 𝗎𝗌𝗂𝗇𝗀 /id 𝗂𝗇 𝗍𝗁𝖾 𝗀𝗋𝗈𝗎𝗉"
            )
            return
        
        try:
            group_id = int(context.args[0])
        except ValueError:
            await update.message.reply_text("❌ 𝖨𝗇𝗏𝖺𝗅𝗂𝖽 𝗀𝗋𝗈𝗎𝗉 𝖨𝖣!")
            return
        
        # Add connection to database
        success = await self.db.add_connection(user_id, group_id)
        
        if success:
            await update.message.reply_text(
                f"✅ 𝖦𝗋𝗈𝗎𝗉 `{group_id}` 𝖼𝗈𝗇𝗇𝖾𝖼𝗍𝖾𝖽!\n"
                "𝖸𝗈𝗎 𝖼𝖺𝗇 𝗇𝗈𝗐 𝗎𝗌𝖾 𝖻𝗈𝗍 𝖿𝖾𝖺𝗍𝗎𝗋𝖾𝗌 𝗂𝗇 𝗉𝗋𝗂𝗏𝖺𝗍𝖾.",
                parse_mode=ParseMode.MARKDOWN
            )
        else:
            await update.message.reply_text("❌ 𝖥𝖺𝗂𝗅𝖾𝖽 𝗍𝗈 𝖼𝗈𝗇𝗇𝖾𝖼𝗍 𝗀𝗋𝗈𝗎𝗉.")
    
    async def show_connections(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show connected groups"""
        user_id = update.effective_user.id
        
        # Log stats
        await self.db.log_stats("show_connections", user_id, update.effective_chat.id)
        
        connection = await self.db.get_connection(user_id)
        
        if not connection:
            await update.message.reply_text("📭 𝖭𝗈 𝖼𝗈𝗇𝗇𝖾𝖼𝗍𝖾𝖽 𝗀𝗋𝗈𝗎𝗉𝗌!")
            return
        
        group_id = connection['group_id']
        connected_at = connection['connected_at'].strftime("%Y-%m-%d %H:%M")
        
        await update.message.reply_text(
            f"🔗 *𝖢𝗈𝗇𝗇𝖾𝖼𝗍𝖾𝖽 𝖦𝗋𝗈𝗎𝗉:*\n"
            f"𝖨𝖣: `{group_id}`\n"
            f"𝖢𝗈𝗇𝗇𝖾𝖼𝗍𝖾𝖽 𝖺𝗍: {connected_at}",
            parse_mode=ParseMode.MARKDOWN
        )
    
    async def disconnect_group(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Disconnect from group"""
        user_id = update.effective_user.id
        
        # Log stats
        await self.db.log_stats("disconnect_group", user_id, update.effective_chat.id)
        
        connection = await self.db.get_connection(user_id)
        
        if not connection:
            await update.message.reply_text("❌ 𝖭𝗈 𝖺𝖼𝗍𝗂𝗏𝖾 𝖼𝗈𝗇𝗇𝖾𝖼𝗍𝗂𝗈𝗇!")
            return
        
        group_id = connection['group_id']
        success = await self.db.delete_connection(user_id)
        
         if success:
            await update.message.reply_text(f"✅ 𝖣𝗂𝗌𝖼𝗈𝗇𝗇𝖾𝖼𝗍𝖾𝖽 𝖿𝗋𝗈𝗆 𝗀𝗋𝗈𝗎𝗉 `{group_id}`", parse_mode=ParseMode.MARKDOWN)
        else:
            await update.message.reply_text("❌ 𝖥𝖺𝗂𝗅𝖾𝖽 𝗍𝗈 𝖽𝗂𝗌𝖼𝗈𝗇𝗇𝖾𝖼𝗍.")
    
    async def add_channel_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Add channel to database"""
        user_id = update.effective_user.id
        chat_id = update.effective_chat.id
        
        # Log stats
        await self.db.log_stats("add_channel", user_id, chat_id)
        
        # Check if user is admin in database
        is_admin = await self.db.is_admin(chat_id, user_id)
        if not is_admin:
            await update.message.reply_text("❌ 𝖸𝗈𝗎 𝗇𝖾𝖾𝖽 𝖺𝖽𝗆𝗂𝗇 𝗋𝗂𝗀𝗁𝗍𝗌 𝗍𝗈 𝖺𝖽𝖽 𝖼𝗁𝖺𝗇𝗇𝖾𝗅𝗌!")
            return
        
        if not context.args:
            await update.message.reply_text(
                "❌ 𝖴𝗌𝖺𝗀𝖾: /addchannel channel_id title\n"
                "𝖤𝗑𝖺𝗆𝗉𝗅𝖾: /addchannel -1001234567890 Anime Channel"
            )
            return
        
        try:
            channel_id = int(context.args[0])
            title = ' '.join(context.args[1:]) if len(context.args) > 1 else "Untitled Channel"
        except ValueError:
            await update.message.reply_text("❌ 𝖨𝗇𝗏𝖺𝗅𝗂𝖽 𝖼𝗁𝖺𝗇𝗇𝖾𝗅 𝖨𝖣!")
            return
        
        # Add channel to database
        success = await self.db.add_channel(channel_id, title, user_id)
        
        if success:
            await update.message.reply_text(
                f"✅ 𝖢𝗁𝖺𝗇𝗇𝖾𝗅 𝖺𝖽𝖽𝖾𝖽 𝗍𝗈 𝖽𝖺𝗍𝖺𝖻𝖺𝗌𝖾!\n"
                f"𝖨𝖣: `{channel_id}`\n"
                f"𝖳𝗂𝗍𝗅𝖾: {title}",
                parse_mode=ParseMode.MARKDOWN
            )
        else:
            await update.message.reply_text("❌ 𝖥𝖺𝗂𝗅𝖾𝖽 𝗍𝗈 𝖺𝖽𝖽 𝖼𝗁𝖺𝗇𝗇𝖾𝗅.")
    
    async def list_channels(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """List all channels in database"""
        user_id = update.effective_user.id
        chat_id = update.effective_chat.id
        
        # Log stats
        await self.db.log_stats("list_channels", user_id, chat_id)
        
        # Get page number from args
        page = 1
        if context.args:
            try:
                page = int(context.args[0])
                if page < 1:
                    page = 1
            except ValueError:
                pass
        
        limit = 10
        skip = (page - 1) * limit
        
        channels, total = await self.db.get_channels(skip, limit)
        
        if not channels:
            await update.message.reply_text("📭 𝖭𝗈 𝖼𝗁𝖺𝗇𝗇𝖾𝗅𝗌 𝗂𝗇 𝖽𝖺𝗍𝖺𝖻𝖺𝗌𝖾!")
            return
        
        channels_text = f"📢 *𝖢𝗁𝖺𝗇𝗇𝖾𝗅𝗌 𝖣𝖺𝗍𝖺𝖻𝖺𝗌𝖾 (Page {page}):*\n\n"
        
        for i, channel in enumerate(channels, 1):
            channel_id = channel['channel_id']
            title = channel['title']
            added_by = channel['added_by']
            added_at = channel['added_at'].strftime("%Y-%m-%d")
            
            channels_text += f"*{i}.* {title}\n"
            channels_text += f"   𝖨𝖣: `{channel_id}`\n"
            channels_text += f"   𝖠𝖽𝖽𝖾𝖽: {added_at}\n\n"
        
        total_pages = (total + limit - 1) // limit
        
        if total_pages > 1:
            channels_text += f"\n📄 *Page {page}/{total_pages}*"
        
        await update.message.reply_text(channels_text, parse_mode=ParseMode.MARKDOWN)
    
    async def delete_channel_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Delete channel from database"""
        user_id = update.effective_user.id
        chat_id = update.effective_chat.id
        
        # Log stats
        await self.db.log_stats("delete_channel", user_id, chat_id)
        
        # Check admin permissions
        is_admin = await self.db.is_admin(chat_id, user_id)
        if not is_admin:
            await update.message.reply_text("❌ 𝖸𝗈𝗎 𝗇𝖾𝖾𝖽 𝖺𝖽𝗆𝗂𝗇 𝗋𝗂𝗀𝗁𝗍𝗌 𝗍𝗈 𝖽𝖾𝗅𝖾𝗍𝖾 𝖼𝗁𝖺𝗇𝗇𝖾𝗅𝗌!")
            return
        
        if not context.args:
            await update.message.reply_text("❌ 𝖴𝗌𝖺𝗀𝖾: /delchannel channel_id")
            return
        
        try:
            channel_id = int(context.args[0])
        except ValueError:
            await update.message.reply_text("❌ 𝖨𝗇𝗏𝖺𝗅𝗂𝖽 𝖼𝗁𝖺𝗇𝗇𝖾𝗅 𝖨𝖣!")
            return
        
        # Check if channel exists
        channel = await self.db.get_channel(channel_id)
        if not channel:
            await update.message.reply_text(f"❌ 𝖢𝗁𝖺𝗇𝗇𝖾𝗅 `{channel_id}` 𝗇𝗈𝗍 𝖿𝗈𝗎𝗇𝖽!", parse_mode=ParseMode.MARKDOWN)
            return
        
        # Delete channel from database
        success = await self.db.delete_channel(channel_id)
        
        if success:
            await update.message.reply_text(f"✅ 𝖢𝗁𝖺𝗇𝗇𝖾𝗅 `{channel_id}` 𝖽𝖾𝗅𝖾𝗍𝖾𝖽!", parse_mode=ParseMode.MARKDOWN)
        else:
            await update.message.reply_text("❌ 𝖥𝖺𝗂𝗅𝖾𝖽 𝗍𝗈 𝖽𝖾𝗅𝖾𝗍𝖾 𝖼𝗁𝖺𝗇𝗇𝖾𝗅.")
    
    async def add_admin_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Add admin to database"""
        user_id = update.effective_user.id
        chat_id = update.effective_chat.id
        
        # Log stats
        await self.db.log_stats("add_admin", user_id, chat_id)
        
        # Only allow in groups
        if update.effective_chat.type not in ['group', 'supergroup']:
            await update.message.reply_text("❌ 𝖳𝗁𝗂𝗌 𝖼𝗈𝗆𝗆𝖺𝗇𝖽 𝖼𝖺𝗇 𝗈𝗇𝗅𝗒 𝖻𝖾 𝗎𝗌𝖾𝖽 𝗂𝗇 𝗀𝗋𝗈𝗎𝗉𝗌!")
            return
        
        # Check if user is Telegram admin
        try:
            user = await update.effective_chat.get_member(user_id)
            if user.status not in [ChatMember.ADMINISTRATOR, ChatMember.OWNER]:
                await update.message.reply_text("❌ 𝖸𝗈𝗎 𝗇𝖾𝖾𝖽 𝖺𝖽𝗆𝗂𝗇 𝗋𝗂𝗀𝗁𝗍𝗌 𝗍𝗈 𝖺𝖽𝖽 𝖺𝖽𝗆𝗂𝗇𝗌!")
                return
        except:
            await update.message.reply_text("❌ 𝖥𝖺𝗂𝗅𝖾𝖽 𝗍𝗈 𝖼𝗁𝖾𝖼𝗄 𝖺𝖽𝗆𝗂𝗇 𝗌𝗍𝖺𝗍𝗎𝗌!")
            return
        
        if not context.args:
            await update.message.reply_text("❌ 𝖴𝗌𝖺𝗀𝖾: /addadmin user_id")
            return
        
        try:
            new_admin_id = int(context.args[0])
        except ValueError:
            await update.message.reply_text("❌ 𝖨𝗇𝗏𝖺𝗅𝗂𝖽 𝗎𝗌𝖾𝗋 𝖨𝖣!")
            return
        
        # Add admin to database
        success = await self.db.add_admin(chat_id, new_admin_id, user_id)
        
        if success:
            await update.message.reply_text(f"✅ 𝖴𝗌𝖾𝗋 `{new_admin_id}` 𝖺𝖽𝖽𝖾𝖽 𝖺𝗌 𝖺𝖽𝗆𝗂𝗇!", parse_mode=ParseMode.MARKDOWN)
        else:
            await update.message.reply_text("❌ 𝖥𝖺𝗂𝗅𝖾𝖽 𝗍𝗈 𝖺𝖽𝖽 𝖺𝖽𝗆𝗂𝗇.")
    
    async def remove_admin_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Remove admin from database"""
        user_id = update.effective_user.id
        chat_id = update.effective_chat.id
        
        # Log stats
        await self.db.log_stats("remove_admin", user_id, chat_id)
        
        # Only allow in groups
        if update.effective_chat.type not in ['group', 'supergroup']:
            await update.message.reply_text("❌ 𝖳𝗁𝗂𝗌 𝖼𝗈𝗆𝗆𝖺𝗇𝖽 𝖼𝖺𝗇 𝗈𝗇𝗅𝗒 𝖻𝖾 𝗎𝗌𝖾𝖽 𝗂𝗇 𝗀𝗋𝗈𝗎𝗉𝗌!")
            return
        
        # Check if user is Telegram admin
        try:
            user = await update.effective_chat.get_member(user_id)
            if user.status not in [ChatMember.ADMINISTRATOR, ChatMember.OWNER]:
                await update.message.reply_text("❌ 𝖸𝗈𝗎 𝗇𝖾𝖾𝖽 𝖺𝖽𝗆𝗂𝗇 𝗋𝗂𝗀𝗁𝗍𝗌 𝗍𝗈 𝗋𝖾𝗆𝗈𝗏𝖾 𝖺𝖽𝗆𝗂𝗇𝗌!")
                return
        except:
            await update.message.reply_text("❌ 𝖥𝖺𝗂𝗅𝖾𝖽 𝗍𝗈 𝖼𝗁𝖾𝖼𝗄 𝖺𝖽𝗆𝗂𝗇 𝗌𝗍𝖺𝗍𝗎𝗌!")
            return
        
        if not context.args:
            await update.message.reply_text("❌ 𝖴𝗌𝖺𝗀𝖾: /removeadmin user_id")
            return
        
        try:
            admin_id = int(context.args[0])
        except ValueError:
            await update.message.reply_text("❌ 𝖨𝗇𝗏𝖺𝗅𝗂𝖽 𝗎𝗌𝖾𝗋 𝖨𝖣!")
            return
        
        # Remove admin from database
        success = await self.db.remove_admin(chat_id, admin_id)
        
        if success:
            await update.message.reply_text(f"✅ 𝖴𝗌𝖾𝗋 `{admin_id}` 𝗋𝖾𝗆𝗈𝗏𝖾𝖽 𝖿𝗋𝗈𝗆 𝖺𝖽𝗆𝗂𝗇𝗌!", parse_mode=ParseMode.MARKDOWN)
        else:
            await update.message.reply_text(f"❌ 𝖴𝗌𝖾𝗋 `{admin_id}` 𝗂𝗌 𝗇𝗈𝗍 𝖺𝗇 𝖺𝖽𝗆𝗂𝗇!", parse_mode=ParseMode.MARKDOWN)
    
    async def show_stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show bot statistics"""
        user_id = update.effective_user.id
        chat_id = update.effective_chat.id
        
        # Log stats
        await self.db.log_stats("show_stats", user_id, chat_id)
        
        # Check if user is admin
        is_admin = await self.db.is_admin(chat_id, user_id)
        if not is_admin:
            await update.message.reply_text("❌ 𝖸𝗈𝗎 𝗇𝖾𝖾𝖽 𝖺𝖽𝗆𝗂𝗇 𝗋𝗂𝗀𝗁𝗍𝗌 𝗍𝗈 𝗏𝗂𝖾𝗐 𝗌𝗍𝖺𝗍𝗌!")
            return
        
        stats = await self.db.get_stats(7)  # Last 7 days
        
        if not stats:
            await update.message.reply_text("📊 𝖭𝗈 𝗌𝗍𝖺𝗍𝗂𝗌𝗍𝗂𝖼𝗌 𝖺𝗏𝖺𝗂𝗅𝖺𝖻𝗅𝖾 𝗒𝖾𝗍!")
            return
        
        stats_text = "📊 *𝖡𝗈𝗍 𝖲𝗍𝖺𝗍𝗂𝗌𝗍𝗂𝖼𝗌 (Last 7 Days):*\n\n"
        stats_text += f"• *𝖳𝗈𝗍𝖺𝗅 𝖢𝗈𝗆𝗆𝖺𝗇𝖽𝗌:* {stats.get('total_commands', 0)}\n"
        stats_text += f"• *𝖴𝗇𝗂𝗊𝗎𝖾 𝖴𝗌𝖾𝗋𝗌:* {stats.get('unique_users', 0)}\n"
        stats_text += f"• *𝖴𝗇𝗂𝗊𝗎𝖾 𝖢𝗁𝖺𝗍𝗌:* {stats.get('unique_chats', 0)}\n\n"
        
        # Command breakdown
        command_breakdown = stats.get('command_breakdown', [])
        if command_breakdown:
            stats_text += "*𝖢𝗈𝗆𝗆𝖺𝗇𝖽 𝖡𝗋𝖾𝖺𝗄𝖽𝗈𝗐𝗇:*\n"
            for day_stats in command_breakdown:
                for cmd, count in day_stats.items():
                    stats_text += f"  • {cmd}: {count}\n"
        
        await update.message.reply_text(stats_text, parse_mode=ParseMode.MARKDOWN)
    
    async def get_id(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Get user or group ID"""
        chat = update.effective_chat
        user = update.effective_user
        
        # Log stats
        await self.db.log_stats("get_id", user.id, chat.id)
        
        if chat.type == 'private':
            await update.message.reply_text(f"👤 *𝖸𝗈𝗎𝗋 𝖨𝖣:* `{user.id}`", parse_mode=ParseMode.MARKDOWN)
        else:
            await update.message.reply_text(
                f"👤 *𝖸𝗈𝗎𝗋 𝖨𝖣:* `{user.id}`\n"
                f"👥 *𝖦𝗋𝗈𝗎𝗉 𝖨𝖣:* `{chat.id}`",
                parse_mode=ParseMode.MARKDOWN
            )
    
    async def get_info(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Get user information"""
        user_id = update.effective_user.id
        chat_id = update.effective_chat.id
        
        # Log stats
        await self.db.log_stats("get_info", user_id, chat_id)
        
        if not context.args:
            await update.message.reply_text("❌ 𝖴𝗌𝖺𝗀𝖾: /info user_id")
            return
        
        try:
            target_id = int(context.args[0])
            user = await context.bot.get_chat(target_id)
            
            info_text = f"""
👤 *𝖴𝗌𝖾𝗋 𝖨𝗇𝖿𝗈𝗋𝗆𝖺𝗍𝗂𝗈𝗇:*
*𝖨𝖣:* `{user.id}`
*𝖥𝗂𝗋𝗌𝗍 𝖭𝖺𝗆𝖾:* {user.first_name}
*𝖫𝖺𝗌𝗍 𝖭𝖺𝗆𝖾:* {user.last_name or '𝖭/𝖠'}
*𝖴𝗌𝖾𝗋𝗇𝖺𝗆𝖾:* @{user.username or '𝖭/𝖠'}
*𝖨𝗌 𝖡𝗈𝗍:* {user.is_bot}
"""
            await update.message.reply_text(info_text, parse_mode=ParseMode.MARKDOWN)
        except Exception as e:
            await update.message.reply_text(f"❌ 𝖤𝗋𝗋𝗈𝗋: {str(e)}")
    
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle incoming messages for filters"""
        chat_id = update.effective_chat.id
        message_text = update.message.text.lower() if update.message.text else ""
        
        # Check if message contains any filter keyword
        filters_list = await self.db.get_filters(chat_id)
        
        for filter_data in filters_list:
            keyword = filter_data['keyword']
            if keyword in message_text:
                response = filter_data['response']
                
                # Parse special formats
                if response.startswith('[Example]'):
                    # Handle button format
                    if '(buttonurl:' in response:
                        parts = response.split('(buttonurl:')
                        text = parts[0].strip('[]')
                        url = parts[1].rstrip(')')
                        keyboard = [[InlineKeyboardButton(text, url=url)]]
                        reply_markup = InlineKeyboardMarkup(keyboard)
                        await update.message.reply_text(
                            "🔘 Button Example:",
                            reply_markup=reply_markup
                        )
                    else:
                        # Regular link format
                        parts = response.split('](')
                        if len(parts) == 2:
                            text = parts[0].strip('[')
                            url = parts[1].rstrip(')')
                            await update.message.reply_text(
                                f"🔗 Link Example: [{text}]({url})",
                                parse_mode=ParseMode.MARKDOWN
                            )
                else:
                    # Regular response
                    await update.message.reply_text(response)
                break
    
    async def error_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle errors"""
        logger.error(f"Update {update} caused error {context.error}")
        try:
            await update.message.reply_text(
                "❌ 𝖠𝗇 𝖾𝗋𝗋𝗈𝗋 𝗈𝖼𝖼𝗎𝗋𝗋𝖾𝖽. 𝖯𝗅𝖾𝖺𝗌𝖾 𝗍𝗋𝗒 𝖺𝗀𝖺𝗂𝗇 𝗅𝖺𝗍𝖾𝗋.\n"
                "𝖨𝖿 𝗉𝗋𝗈𝖻𝗅𝖾𝗆 𝗉𝖾𝗋𝗌𝗂𝗌𝗍𝗌, 𝖼𝗈𝗇𝗍𝖺𝖼𝗍 @Rare_Anime_Chat_Group"
            )
        except:
            pass

async def main():
    """Start the bot"""
    # Get bot token from environment variable
    TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
    
    if TOKEN == "YOUR_BOT_TOKEN_HERE":
        logger.error("Please set BOT_TOKEN environment variable!")
        return
    
    # Create bot instance
    bot = FilterBot(TOKEN)
    
    # Initialize database
    await bot.initialize()
    
    # Create application
    application = Application.builder().token(TOKEN).build()
    
    # Add command handlers
    application.add_handler(CommandHandler("start", bot.start))
    application.add_handler(CommandHandler("add", bot.add_filter))
    application.add_handler(CommandHandler("del", bot.delete_filter))
    application.add_handler(CommandHandler("filters", bot.list_filters))
    application.add_handler(CommandHandler("connect", bot.connect_group))
    application.add_handler(CommandHandler("connections", bot.show_connections))
    application.add_handler(CommandHandler("disconnect", bot.disconnect_group))
    application.add_handler(CommandHandler("addchannel", bot.add_channel_command))
    application.add_handler(CommandHandler("channels", bot.list_channels))
    application.add_handler(CommandHandler("delchannel", bot.delete_channel_command))
    application.add_handler(CommandHandler("addadmin", bot.add_admin_command))
    application.add_handler(CommandHandler("removeadmin", bot.remove_admin_command))
    application.add_handler(CommandHandler("stats", bot.show_stats))
    application.add_handler(CommandHandler("id", bot.get_id))
    application.add_handler(CommandHandler("info", bot.get_info))
    
    # Add message handler for filters
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, bot.handle_message))
    
    # Add error handler
    application.add_error_handler(bot.error_handler)
    
    # Start the bot
    print("🤖 Bot is running with MongoDB support...")
    await application.initialize()
    await application.start()
    await application.updater.start_polling()
    
    # Keep running
    try:
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        print("\n🛑 Bot stopped.")
    finally:
        await application.stop()

if __name__ == '__main__':
    asyncio.run(main())
