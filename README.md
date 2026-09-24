# Streamer Buddy

An AI co-host for live streams.

Streamer Buddy gives you a voice companion that you talk to normally,
out loud, while you stream, and that keeps track of your Twitch
chat at the same time. Allowing for chat integration.
It runs on OpenAI's GPT-Live model over WebRTC,
so the conversation is full duplex: it listens while it speaks, and
you can cut it off mid-sentence the way you would a person.

Chat reaches it two different ways:

- **Viewers can talk to it directly** by prefixing a message with your
  chat command (`!name` by default). Those get answered out loud.
- **Everything else becomes background context.** Ordinary chatter is
  batched up and fed in silently, so it knows what chat has been
  talking about and can bring it up later usually not interrupting you
  every time somebody types.

Who it is, how it sounds, and how it behaves are all yours to write:
the personality and system prompts are editable in the app.

---

## Development setup

Requires **Python 3.11+** and Tk. Tk ships with Python on Windows and
macOS; on Linux it's usually a separate package (`tk` on Arch,
`python3-tk` on Debian/Ubuntu).

```bash
git clone git@github.com:ZappaVinny/streamer-buddy.git
cd streamer-buddy

python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt

python main.py
```

There's also a no-UI mode that logs to the terminal:

```bash
python main.py --headless
```

---

## Setup for use

**1. Get an API key.** Create one at
[platform.openai.com/api-keys](https://platform.openai.com/api-keys).
The account needs access to `gpt-live-1`

**2. Add it to the app.** Open the **General** tab, click **API key…**,
and paste it in. It's stored in your operating system's credential
manager, not in any config file. If you'd rather not store it, setting
the `OPENAI_API_KEY` environment variable works too.

**3. Point it at your channel.** Still in **General**, set the target
channel to your Twitch channel name (just the name, no `#` and no
`twitch.tv/` prefix) and pick the chat command viewers will use.

**4. Check your audio.** In the **Audio** tab, choose your microphone
and speaker, then use **Test microphone** and **Play test tone** to
confirm they work before you go live.

**NOTE: sometimes audio things break and crash, I don't really know why, but just use system default**

**5. Hit Connect.** Talk normally. Nothing is billed until you connect.

---

## Contribution

Anyone can contribute, just put in a PR, and I will review it when I can

---

## Generative AI Usage

This project was primarily developed with the use of generative AI, however, all code was reviewed by a human (Me! I am the human)

---

## License

[MIT](LICENSE) — do what you like with it, just keep the copyright
notice and license text.
