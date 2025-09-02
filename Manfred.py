import discord
import time
from discord.ext import commands
import random
import sqlite3
import google
from google import genai
from google.genai import types
from PIL import Image
from io import BytesIO

# Discord api magic that I don't understand but hey it works
intents = discord.Intents.default()
intents.message_content = True  # Enable message content intent

# Global variable to lock out commands
wall = False

# Global variable to track previous use times
last_use = time.time() - 600

# Length of timeout on commands with limits
timeout = 300

# Read google genai api key from file
with open("key.txt", 'r') as file:
    client = genai.Client(api_key=file.readline())

# Add image to db using existing connection
def insert_image(connection, image_id, name, image_data):
    cursor = connection.cursor()
    cursor.execute("INSERT OR REPLACE   INTO images (id, name, image_data) VALUES (?, ?, ?)",
                   (image_id, name, image_data))
    connection.commit()
    cursor.close()


bot = commands.Bot(command_prefix='!', intents=intents)


@bot.event
async def on_ready():
    print(f'Logged in as the {bot.user.name}')


@bot.command()
async def fuse(ctx):
    global last_use
    # Check if timeout has not yet elapsed
    if (time.time() - last_use) < timeout:
        line = "gotta wait " + str(round(timeout - (time.time() - last_use))) + " seconds buddy"
        await ctx.send(line)
        return


    last_use = time.time()
    # Prompt for the model to use, purposefully generic as it has to match two random images
    text_input = """create a combination of these two images, generate a generic background if neither image has one, otherwise use a background from one of the images, attempt to replace parts of one image with the other where they even vaguely match up, try and stylize the image so that the integrated image has a tone consistent witht the base"""

    # Fetch two images to merge from db randomly
    connection = sqlite3.connect('images.db')
    cursor = connection.cursor()
    cursor.execute("SELECT * FROM images ORDER BY RANDOM() LIMIT 2")

    image_one = cursor.fetchone()

    image_two = cursor.fetchone()

    cursor.close()
    connection.close()

    with open('temp_image1.jpg', 'wb') as file:
        file.write(image_one[2])

    with open('temp_image2.jpg', 'wb') as file:
        file.write(image_two[2])

    # Check if images have been found and hand off to the model to merge
    if image_one is not None and image_two is not None:
        response = client.models.generate_content(
            model="gemini-2.5-flash-image-preview",
            contents=[Image.open('temp_image1.jpg'), Image.open('temp_image2.jpg'), text_input],
        )
        image_parts = [
            part.inline_data.data
            for part in response.candidates[0].content.parts
            if part.inline_data
        ]

        if image_parts:
            image = Image.open(BytesIO(image_parts[0]))
            image.save('fused.png')
            discord_file = discord.File('fused.png', filename="fused.png")
            im1 = discord.File('temp_image1.jpg', filename="fused.png")
            im2 = discord.File('temp_image2.jpg', filename="fused.png")

            # Send merged image and the components
            await ctx.send(files=[discord_file, im1, im2])

    else:
        await ctx.send("No images found in the database.")


# Retrieve random image from db and send to called chanel
@bot.command()
async def summon(ctx):
    connection = sqlite3.connect('images.db')
    cursor = connection.cursor()
    cursor.execute("SELECT * FROM images ORDER BY RANDOM() LIMIT 1")
    random_result = cursor.fetchone()
    cursor.close()
    connection.close()

    if random_result is not None:
        image_id = random_result[0]
        name = random_result[1]
        image_data = random_result[2]

        with open('temp_image.jpg', 'wb') as file:
            file.write(image_data)

        discord_file = discord.File('temp_image.jpg', filename=name)
        await ctx.send(file=discord_file)
    else:
        await ctx.send("No images found in the database.")


# Search specified channel and update database with its contents
@bot.command()
@discord.ext.commands.is_owner()
async def update(ctx):
    global wall
    await ctx.send('Yea okay buddy')
    if wall:
        await ctx.send('cut that shit')
        return

    wall = True

    channel_id = 775131022169341972
    channel = bot.get_channel(channel_id)
    connection = sqlite3.connect('images.db')
    messages_with_attachments = []

    # Collect all message attachments and loop through them adding each to the db
    try:
        async for msg in channel.history(limit=400):
            if msg.attachments:
                messages_with_attachments.append(msg)
                for attachment in msg.attachments:
                    image_data = await attachment.read()
                    insert_image(connection, attachment.id, attachment.filename, image_data)
    except Exception as e:
        await ctx.send(f"An error occurred during the update: {str(e)}")
    finally:
        connection.close()
        wall = False

    await ctx.send("shit worked")


@bot.command()
async def quote(ctx, member: discord.Member = None, ):
    channel_id = 1028021322728603749
    channel = bot.get_channel(channel_id)
    messages = []

    async for message in channel.history(limit=100):
        messages.append(message)

    if member is not None:
        messages = [msg for msg in messages if msg.author == member]

    if len(messages) == 0:
        await ctx.send("Couldn't find shit")
        return

    random_message = random.choice(messages)
    quote_text = f'{random_message.content} - {random_message.author.name}'

    if random_message.attachments:
        attachment_urls = [attachment.url for attachment in random_message.attachments]
        quote_text += f' {", ".join(attachment_urls)}'

    await ctx.send(quote_text)

# Run bot with discord bot api key
with open('discKey.txt', 'r') as file:
    bot.run(file.readline())
