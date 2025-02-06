from PIL import Image

# Convert PNG to ICO
img = Image.open('icon.png')
img.save('icon.ico', format='ICO')