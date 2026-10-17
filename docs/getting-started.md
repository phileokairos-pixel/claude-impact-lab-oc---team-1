# Getting started

From sitting down to building.

## 1. Get the files

Pick whichever fits your team. You can switch later.

**Option A: a team repo on GitHub.** Best if anyone on the team will write code. One person does
this:

1. On this repo's GitHub page, choose **Use this template**, then **Create a new repository**.
2. Name it for your team, set it to **Public**, and create it.
3. Add your teammates under Settings, then Collaborators.
4. Everyone gets a copy: `git clone https://github.com/YOUR-NAME/YOUR-REPO.git`, or
   **Code**, then **Open with GitHub Desktop**.

Keep the license file. When you start writing about your project, replace the top-level
`README.md` with [`templates/TEAM-README.md`](../templates/TEAM-README.md).

**Option B: download a ZIP.** Fastest if nobody on the team uses GitHub. On this repo's page,
choose **Code**, then **Download ZIP**, and unzip it. You still need one public GitHub repo by
4:00 PM to submit; an organizer can help you make it in five minutes.

Either way, the template's own files do not count as your work. What you add after 9:30 AM does.

## 2. Pick how you work with Claude

All three work for every challenge.

| | How | Good for |
|---|---|---|
| **In the browser** | Open [claude.ai](https://claude.ai), start a project, and add the files for your challenge | Teams that do not code |
| **Claude Code in the desktop app** | Install the [Claude app](https://claude.ai/download), open Claude Code and choose your folder | Building without a terminal |
| **Claude Code in a terminal** | Install from [claude.com/claude-code](https://claude.com/claude-code), then run `claude` in your folder | Developers |

Claude Code reads [`CLAUDE.md`](../CLAUDE.md) when it starts, so it already knows the event rules
and where the data is. In the browser, add `CLAUDE.md` to your project too.

Event credits: $100 in Claude API credits per person (API only, not Claude.ai). Claim at https://platform.claude.com/offers/e6957ff5-5a6b-438e-957b-d6a2a8efffba using your Org ID from [console.anthropic.com](https://console.anthropic.com), not your Claude.ai ID. One claim per person.

## If you do not write code

You are needed. Teams with someone who knows the work build better things. You can:

- Write the test cases. What would a real coordinator, client or nurse try?
- Read every output and say what is wrong with it.
- Write the words on the screen in plain language.
- Run the demo.

You can also build. Describe what you want to Claude in plain words and it will write the code.

## Working with the faxed packets (Challenge 1)

- [Download the packets](https://drive.google.com/drive/folders/1ISmUtoNCTW3NJNqCQJHJzb6C319RgrXM) into `challenges/1-referral-intake/packets/` first. They are not in
  the repo.
- The PDFs have no text layer. Claude Code can read them directly as page images.
- Simple OCR gets most words right and still mangles some. Check numbers and dates.

## Keep your work safe

- Commit and push often.
- Keep API keys in environment variables. `.env` is already in `.gitignore`.
- No identifiable patient information, and do not copy the packets into your repo. See the
  [ground rules](ground-rules.md).

## Submit by 4:00 PM

See [submission.md](submission.md).
