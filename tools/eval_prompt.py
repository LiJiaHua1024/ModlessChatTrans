# Prompt A/B eval harness — derives system prompts from the real Translator
# code and mirrors production request params (temperature=0, max_tokens, usage).
#
# Usage:  python tools/eval_prompt.py [path-to-config.toml]
# Requires a TOML config containing a working OpenRouter api-key.
# Writes raw outputs to _eval_results.jsonl in the cwd; prints per-variant
# suspect counts before AND after the single-line collapse net.
import json
import sys
import time
import tomllib
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from modless_chat_trans.translator import Translator

CFG_PATH = sys.argv[1] if len(sys.argv) > 1 else "modless-chat-trans.toml"
CFG = tomllib.load(open(CFG_PATH, "rb"))
LLM = CFG["player-translation"]["llm"]
TARGET = CFG["message-capture"]["target-language"]

B_PROMPT = Translator._build_player_normal_prompt(object.__new__(Translator), has_context=False)

B_BLOCK = (
    "\nDo not think aloud — this is a hard rule. The reply is pasted into the "
    "chat window and read aloud by TTS, so every word you output is shown and "
    "spoken. Resolve ambiguity, misspellings, and candidate readings silently; "
    "the reply contains the chosen wording only — never your reasoning, "
    "options, notes, or corrections.\n"
)
TAIL = "\nReply with the translation only: a single line, nothing else.\n"
assert B_BLOCK in B_PROMPT and TAIL in B_PROMPT, "prompt drifted"

A_BULLET = (
    "- Deliberation: Weigh options silently. Never narrate reasoning, list "
    "candidates, or add notes — the reply is the chosen wording only.\n"
)
A_PROMPT = B_PROMPT.replace(B_BLOCK, A_BULLET)
O_PROMPT = B_PROMPT.replace(B_BLOCK, "")  # original: no deliberation rule at all

INPUTS = [
    # term-recognition triggers (real cache entries + MC/PvP jargon)
    "whats telly.", "telly but faster", "no way to can telly bridge",
    "how can u telly bruidgwe", "yea i telly",
    "i can speed telly on eu servers", "whats speed telly",
    "cuz normally telly doesnt work bcs of the server",
    "he hit a sick block clutch", "nice god bridge", "w-tap him",
    "that butterfly click is insane", "bro is jitter clicking 20 cps",
    "get combo'd", "he just rod tricked me", "nice strafe",
    "he's spawn trapping us", "stop stream sniping", "he's b-hopping",
    "MLG water", "he fisted me to death", "totem popped",
    "he's on a 200 ws", "hit a 4 block flat",
    # requires-a-leap slang
    "the audacity", "caught in 4k", "rent free", "bro fumbled the bag",
    "NPC behavior", "that map is mid", "based take", "cope harder",
    "seethe and mald", "he's cooked", "ate that up", "bro got humbled",
    "no shot he said that", "out of pocket", "ping diff", "that's so cap",
    "sheeeeesh", "he's himothy",
    # confirmed hard cases
    "nehter", "to ty od gombka ?", "need dia", "u 3 in party?",
    # normals (regression check)
    "gg wp that was insane", "brb dinner",
    "yo anyone got spare iron? i lost all my stuff to that trap near spawn",
    # pure keyboard mashing (control: rarely triggers)
    "asdkfjh lol", "wwwwww", "bridghe [ls",
]
ROUNDS = 4

MARKERS = ["wait", "note:", "options", "(", "（", "—", "actually", "means",
           "misspell", "typo", "alternat", "or simply", "correct", "let me",
           "looking at", "hmm", "i think", "翻译", "候选", "注", " / ", "->",
           "“", "”", '"']


def looks_verbose(text):
    t = text.strip()
    if "\n" in t:
        return True
    low = t.lower()
    return any(m in low for m in MARKERS)


def collapse(text):
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    return lines[-1] if len(lines) > 1 else text.strip()


def call(prompt, text):
    user = (
        f"Translate the text in <text_to_translate> to {TARGET}.\n\n"
        f"<text_to_translate>\n{text}\n</text_to_translate>\n\n"
        "Reply with only the final translation."
    )
    body = json.dumps({
        "model": LLM["model"],
        "messages": [{"role": "system", "content": prompt},
                     {"role": "user", "content": user}],
        "temperature": 0,
        "max_tokens": LLM["max-tokens"],
        "usage": {"include": True},
    }).encode()
    req = urllib.request.Request(
        "https://openrouter.ai/api/v1/chat/completions", data=body,
        headers={"Authorization": f"Bearer {LLM['api-key']}",
                 "Content-Type": "application/json"})
    last_err = None
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                d = json.load(r)
            u = d.get("usage") or {}
            return d["choices"][0]["message"]["content"].strip(), \
                u.get("cost") or 0, u
        except Exception as e:
            last_err = e
            time.sleep(2 * (attempt + 1))
    return f"<ERROR {last_err}>", 0, {}


VARIANTS = ("O", "A", "B")
prompts = {"O": O_PROMPT, "A": A_PROMPT, "B": B_PROMPT}
jobs = [(v, t, r) for v in VARIANTS for r in range(ROUNDS) for t in INPUTS]
results, total_cost, total_toks = [], 0.0, 0

with ThreadPoolExecutor(4) as ex:
    for v, t, r, out, cost, u in ex.map(
            lambda j: (*j, *call(prompts[j[0]], j[1])), jobs):
        results.append((v, t, r, out))
        total_cost += cost
        total_toks += u.get("prompt_tokens", 0) + u.get("completion_tokens", 0)

with open("_eval_results.jsonl", "w", encoding="utf-8") as f:
    for v, t, r, out in results:
        f.write(json.dumps({"v": v, "in": t, "round": r, "out": out},
                           ensure_ascii=False) + "\n")

print(f"calls={len(jobs)} tokens={total_toks} cost=${total_cost:.4f}")
for v in VARIANTS:
    vr = [x for x in results if x[0] == v]
    raw = [x for x in vr if looks_verbose(x[3])]
    resid = [x for x in vr if looks_verbose(collapse(x[3]))]
    per_round = [sum(1 for s in raw if s[2] == r) for r in range(ROUNDS)]
    print(f"[{v}] raw={len(raw)}/{len(vr)} {per_round} "
          f"post-collapse-residual={len(resid)}")
    for _, t, r, out in raw:
        print(f"  r{r} {t!r} -> {out!r}")
    for _, t, r, out in resid:
        print(f"  RESIDUAL r{r} {t!r} -> {collapse(out)!r}")
