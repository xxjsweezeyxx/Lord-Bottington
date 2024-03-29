import os #used for loading secrets (tokens, codes, passwords, etc.)
import discord #needed to interact with discord API
import random #used for choosing random selections from lists
from discord.ext import tasks #used to start various loop tasks
from discord.ext import commands #used for slash commands
import pymongo #used for database management
from dotenv import load_dotenv
import datetime
import pytz
import json
import requests
import asyncio


#This checks if the person running the code has a token for discord API or not
try:
    # Load environment variables from .env
    load_dotenv()
  
    #Important variables (tokens, codes, passwords, files, etc.)
    token = os.getenv('token')
except:
    print("Apologies good sir, but it appears that you require a Discord API key to access my features.\n\nPlease visit the following link to learn how to do such things:\n\nhttps://discord.com/developers/docs/getting-started")
    exit()
    

#set up the bot's prefix command and intents
bot = commands.Bot(intents=discord.Intents.all())
bot.remove_command('help')


#ON READY EVENT LISTENER
@bot.event
async def on_ready():
  #begin changing Lord Bottington's activities
  if not change_activity.is_running():
      change_activity.start()

  server_ids = []
  for guild in bot.guilds:
      server_ids.append(guild.id)
    
  #post command list to discordbotlist
  await post_command_list()

  #begin posting Lord Bottington stats to sites
  if not update_stats.is_running():
      update_stats.start()

  #initialize the mongoDB database and get the server IDs for the autopurge command to initiate
  # mongoDBpass = os.environ['mongoDBpass'] #load the mongoDB url (retreived from mongoDB upon account creation)
  mongoDBpass = os.getenv('mongoDBpass')
  client = pymongo.MongoClient(mongoDBpass) # Create a new client and connect to the server
  autopurge_db = client.autopurge_db #create the autpourge database on mongoDB
  bump_db = client.bump_db #create the bump (promotion) database on MongoDB

  #purge all channels that have a limit of 0 messages
  for server_id in server_ids: #for every active server, create a loop task for autopurge
      # Retrieve autopurge configurations from database
      autopurge_config = autopurge_db[f"autopurge_config_{server_id}"].find()
      if autopurge_config:
          for config in autopurge_config:
              messagecount = config['messagecount']
              
              if not messagecount or messagecount == 0:
                  channel_id = config['purge_channel_id']
                  channel = bot.get_channel(channel_id)

                  messages = await channel.history(limit=None).flatten()

                  if len(messages) > 0:
                      await channel.purge(limit=None, check=lambda m: not m.pinned)
    
  # Get all cooldown entries from the database (for cooldowns on promotions)
  cooldown_data_list = bump_db.cooldowns.find()
    
  current_time = datetime.datetime.utcnow()

  if cooldown_data_list:
      for cooldown_data in cooldown_data_list:
          cooldown_time = int(cooldown_data['cooldown']) #convert to integer
          guild_id = cooldown_data['server_id']

          # Update the 'start_time' field in the MongoDB collection
          bump_db.cooldowns.update_one(
              {'_id': cooldown_data['_id']},  # Use the _id field to identify the document
              {'$set': {'start_time': current_time}}
          )
          
          utility_cog = bot.get_cog('Utility') #get the utility cog
          try:
              asyncio.create_task(utility_cog.send_reminder(cooldown_time, guild_id))
          except:
              continue

    
  # Set the timezone to US/Central
  us_central_tz = pytz.timezone('US/Central')
  current_time_utc = datetime.datetime.utcnow()

  # Convert the UTC time to US/Central timezone
  current_time_us_central = current_time_utc.astimezone(us_central_tz)

  # Format the datetime
  formatted_time = current_time_us_central.strftime('%A %B %d, %Y %I:%M %p US/Central')

  #let user of bot know that bot is ready in Console
  print(f"Greetings sir, {bot.user.name} at your service.\nMy current latency is {int(bot.latency*100)} ms, as of {formatted_time}.")
  print("--------------------")



#get list of cogs
cogfiles = [
  f"cogs.{filename[:-3]}" for filename in os.listdir("./cogs/") if filename.endswith(".py")
]

#load all cogs
for cogfile in cogfiles:
  try:
    bot.load_extension(cogfile)
  except Exception as err:
    print(err)



################ UPDATE SERVER COUNT ON SITES ###################
@tasks.loop(minutes=180) #update every 3 hours
async def update_stats():
    server_ids = []
    for guild in bot.guilds:
        server_ids.append(guild.id)

    #post bot stats to discordbotlist
    await post_bot_stats(len(server_ids))


################ UPDATE SERVER COUNT ON SITES ###################




################## CHANGE BOT ACTIVITIES ON DISCORD ################
# Change bots custom status every 10 minutes
@tasks.loop(minutes=10)
async def change_activity():
  with open("text_files/activities.txt", "r") as f:
      activities_full = f.read().splitlines()
    
  activity = random.choice(activities_full)
  current_activity = discord.Activity(type=discord.ActivityType.watching,
                   name = activity)
  await bot.change_presence(activity=current_activity)
################## CHANGE BOT ACTIVITIES ON DISCORD ################



####################### POST COMMAND LIST ##########################
async def post_command_list():
  with open("json_files/commandlist.json", "r") as f:
      command_list = json.load(f)

  bot_id = os.getenv('botID')

  # discordbotlist token
  bot_token = os.getenv('discordbotlist_token')

  # URL for the API endpoint to post commands
  url = f'https://discordbotlist.com/api/v1/bots/{bot_id}/commands'

  # Headers for the POST request (include your bot token for authorization)
  headers = {
      'Authorization': f'Bot {bot_token}'
  }

  # Make the POST request to the API endpoint
  response = requests.post(url, json=command_list, headers=headers)

  # Check the response status
  if response.status_code == 200:
      print('Automaton commands successfully posted to DiscordBotList.')
  else:
      print(f'Failed to post commands to DiscordBotList.\nStatus code: {response.status_code}')
      print(response.text)  # Print the response content for debugging if needed

####################### POST COMMAND LIST ##########################



####################### POST BOT STATS ##########################
async def post_bot_stats(guild_count):
  bot_id = os.getenv('botID') #bot id from discord developer portal

  # site tokens for bot
  bot_token_DBL = os.getenv('discordbotlist_token') # discordbotlist token
  bot_token_topgg = os.getenv('topggToken') # top.gg token

  # URLs for the API endpoint to post commands
  url_DBL = f'https://discordbotlist.com/api/v1/bots/{bot_id}/stats'
  url_topgg = f'https://top.gg/api/bots/{bot_id}/stats'

  # Headers for the POST request (include your bot token for authorization)
  #headers for discordbotlist
  headers_DBL = {
      'Authorization': f'{bot_token_DBL}'
  }

  #headers for top.gg
  headers_topgg = {
      'Authorization': f'{bot_token_topgg}'
  }

  ### DISCORDBOTLIST
  # Make the POST request to the discordbotlist API endpoint
  response_DBL = requests.post(url_DBL, data={"guilds": guild_count}, headers=headers_DBL) #response from discordbotlist

  # Check the response status
  if response_DBL.status_code == 200:
      print('Automaton statistics successfully posted to DiscordBotList.')
  else:
      print(f'Failed to post automaton statistics to DiscordBotList.\nStatus code: {response_DBL.status_code}')
      print(response_DBL.text)  # Print the response content for debugging if needed


  ### TOP.GG
  # Make the POST request to the discordbotlist API endpoint
  response_topgg = requests.post(url_topgg, json={"server_count": guild_count}, headers=headers_topgg) #response from top.gg

  # Check the response status
  if response_topgg.status_code == 200:
      print('Automaton statistics successfully posted to top.gg.')
  else:
      print(f'Failed to post automaton statistics to top.gg.\nStatus code: {response_topgg.status_code}')
      print(response_topgg.text)  # Print the response content for debugging if needed

####################### POST BOT STATS ##########################


# run the bot using the discord API key
try:
    bot.run(token)
except TypeError:
    print("Apologies good sir, but it appears that you require a Discord API key to access my features.\n\nPlease visit the following link to learn how to do such things:\n\nhttps://discord.com/developers/docs/getting-started")
    exit()
