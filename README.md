# Unity-Asset-Ripper

A Python-based tool for directly ripping Unity assets from compiled games.

---

## How It Works

Unity-Asset-Ripper provides an intuitive GUI to help you extract assets from Unity-based games. Below is a guide on how to use it:

---

### **Input Source**

Provide the path to your `Game_Data` folder. You can either select a specific file or the entire folder.

**Example path:**
C:/Users/<YourUser>/OneDrive/Desktop/YourGame/YourGame_Data
---

### **Output Destination**

Specify the folder where the extracted Unity assets will be saved. 

---

### **Extraction Options**

Use the checkboxes to enable or disable specific asset extraction options. You can also turn on/off verbose logging to get more detailed debug information.

- **Verbose Logging:** Toggle on for more detailed debug output during extraction.

---

## Extraction Options Details

- **Textures**: Extract all textures from the game.
- **Sprites**: Extract sprite images.
- **Audio**: Extract audio files.
- **Meshes**: Extract mesh assets.
- **Texts**: Extract in-game text data.
- **Fonts**: Extract font files.
- **Scripts**: Extract script files.
- **Materials**: Extract material files.

---

## Example Usage

1. Launch the program and select your input folder (the `Game_Data` folder).
2. Choose the output folder where the extracted assets will be saved.
3. Select the asset types to extract (Textures, Sprites, Audio, etc.).
4. Start the extraction process.

Verbose logging is available for troubleshooting if needed.
