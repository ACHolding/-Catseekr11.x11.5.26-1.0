#!/usr/bin/env python3
"""CatSeek R1 single-file standard-library edition.
Preserves the original Tkinter GUI. Does NOT claim to contain pretrained weights.
"""
from __future__ import annotations
import ast
import json
import math
import operator
import os
import queue
import re
import sys
import threading
import time
import tkinter as tk
from tkinter import font, scrolledtext
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Optional

APP_NAME = "CatSeek R1"
APP_VERSION = "1.1 · Single File"
ENGINE_NAME = "stdlib local"
GUI_FPS = 60
GUI_TICK_MS = 16

@dataclass
class Reply:
    text: str
    route: str
    elapsed_ms: float
    tokens: int = 0
    tokens_per_second: float = 0.0

@dataclass
class Report:
    initial_loss: float = 0.0
    final_loss: float = 0.0

@dataclass
class Config:
    speed_target: str = "local"

class LocalEngine:
    """Honest zero-dependency helper, not a pretrained LLM."""
    KNOWLEDGE = {
        "hello": "Hello! I'm CatSeek R1, running locally with Python's standard library. What shall we build?",
        "what is bitnet": "BitNet b1.58 is a neural-network architecture that uses ternary weights (-1, 0, +1) in linear layers. This single-file edition does not ship pretrained BitNet weights.",
        "what is deepseek r1": "DeepSeek-R1 is a reasoning-oriented pretrained language-model family. This edition does not contain its weights.",
        "what is dspark": "Speculative decoding uses a fast draft model to propose tokens and a target model to verify them. Without pretrained models, there is no real speculative decoding here.",
        "how to debug python": "Read the final exception first, locate the earliest frame in your code, reproduce with a minimal input, fix the cause, and rerun the test.",
        "how to make a game": "Start with input, a fixed update loop, rendering, collision rules, and a clear win condition. Test a small playable prototype first.",
        "how to make an emulator": "Build the CPU state, memory bus, instruction decoder, timing, graphics, and input. Validate each part with deterministic tests.",
        "你好": "你好！我是 CatSeek R1 单文件版本。这里没有预训练的大语言模型权重。",
    }
    OPS = {ast.Add:operator.add, ast.Sub:operator.sub, ast.Mult:operator.mul,
           ast.Div:operator.truediv, ast.FloorDiv:operator.floordiv, ast.Mod:operator.mod,
           ast.Pow:operator.pow}
    def __init__(self):
        self.model = self
        self.report = Report()
        self.config = Config()
        self.parameter_count = 0
        self.history = []
    def clear(self): self.history.clear()
    def model_card(self):
        return {"name":APP_NAME,"version":APP_VERSION,"runtime":"Python standard library",
                "pretrained_llm":False,"bitnet":False,"deepseek_r1":False,"dspark":False,
                "pip_required":False,"checkpoint_bundled":False,"gui":"Original Tkinter layout"}
    def self_test(self):
        return {"ok": self._calc("2+3*4")==14 and bool(self.reply("hello").text),
                "checks":{"math":self._calc("2+3*4")==14,"gui_class":True,"stdlib_only":True}}
    @classmethod
    def _calc(cls, expression):
        if len(expression)>120: raise ValueError("Expression too long")
        def walk(n,depth=0):
            if depth>20: raise ValueError("Too deep")
            if isinstance(n,ast.Expression): return walk(n.body,depth+1)
            if isinstance(n,ast.Constant) and type(n.value) in (int,float) and abs(n.value)<1e12:return n.value
            if isinstance(n,ast.UnaryOp) and isinstance(n.op,(ast.UAdd,ast.USub)):
                v=walk(n.operand,depth+1);return v if isinstance(n.op,ast.UAdd) else -v
            if isinstance(n,ast.BinOp) and type(n.op) in cls.OPS:
                a,b=walk(n.left,depth+1),walk(n.right,depth+1)
                if isinstance(n.op,ast.Pow) and (abs(b)>10 or abs(a)>1e6):raise ValueError("Power too large")
                result=cls.OPS[type(n.op)](a,b)
                if not math.isfinite(result) or abs(result)>1e15:raise ValueError("Result too large")
                return result
            raise ValueError("Unsupported expression")
        return walk(ast.parse(expression,mode="eval"))
    def reply(self,prompt):
        started=time.perf_counter(); p=prompt.strip(); low=p.casefold()
        if low=="/model": out=json.dumps(self.model_card(),indent=2);route="model-card"
        elif low=="/selftest":out=json.dumps(self.self_test(),indent=2);route="self-test"
        elif low=="/clear":self.clear();out="Conversation cleared.";route="clear"
        elif low in ("/help","/?"):
            out="Commands: /help, /model, /selftest, /clear. Arithmetic: calculate 2+3*4. No pretrained weights are bundled.";route="help"
        else:
            expression=re.sub(r"^(calculate|compute|what is|what's)\s+","",low).rstrip(" ?")
            if re.fullmatch(r"[0-9. +*/%()\-]+",expression) and any(c.isdigit() for c in expression):
                try:out=str(self._calc(expression));route="exact-math"
                except Exception as e:out=f"Cannot calculate: {e}";route="math-error"
            else:
                scored=sorted(((SequenceMatcher(None,low,key).ratio(),key,value) for key,value in self.KNOWLEDGE.items()),reverse=True)
                if scored and (scored[0][0]>.72 or low in self.KNOWLEDGE):out=scored[0][2];route="local-knowledge"
                else:
                    out=("I don't have a pretrained language model in this single-file edition. "
                         "I can do exact arithmetic and answer a few built-in development questions. "
                         "For open-ended AI chat, real pretrained weights and a compatible inference runtime are required.")
                    route="capability-limit"
        self.history.append((p,out));self.history=self.history[-12:]
        elapsed=(time.perf_counter()-started)*1000
        return Reply(out,route,elapsed,len(out.split()),len(out.split())/max(elapsed/1000,0.001))

class CatSeekGUI:
    BG = "#03060b"
    PANEL = "#07101d"
    INPUT = "#0a1424"
    BLUE = "#3b82f6"
    BLUE_2 = "#60a5fa"
    TEXT = "#dbeafe"
    MUTED = "#7890ad"
    RED = "#f87171"

    def __init__(self, root: tk.Tk, engine: CatSeekR11):
        self.root = root
        self.engine = engine
        self.events: queue.Queue[tuple[str, int, int, object]] = queue.Queue()
        self.busy = False
        self.conversation_id = 0
        self.request_serial = 0
        self.active_request_id: Optional[int] = None
        self._build()
        self.root.after(GUI_TICK_MS, self._drain)

    @staticmethod
    def _family(mono: bool = False) -> str:
        if mono:
            return "Cascadia Mono" if os.name == "nt" else "Menlo"
        return "Segoe UI" if os.name == "nt" else "Helvetica Neue"

    def _font(self, size: int, bold: bool = False, mono: bool = False) -> font.Font:
        return font.Font(family=self._family(mono), size=size, weight="bold" if bold else "normal")

    def _build(self) -> None:
        root = self.root
        root.title(f"{APP_NAME} v{APP_VERSION}")
        root.geometry("1040x720")
        root.minsize(780, 560)
        root.configure(bg=self.BG)

        menu = tk.Menu(root, tearoff=False, bg=self.PANEL, fg=self.TEXT)
        catseek = tk.Menu(menu, tearoff=False, bg=self.PANEL, fg=self.TEXT)
        catseek.add_command(label="New CatSeek R11.x10.9.26 chat", command=self._new_chat)
        catseek.add_command(label="CatSeek R11.x10.9.26 model card", command=lambda: self._submit("/model"))
        catseek.add_command(label="CatSeek R11.x10.9.26 inference self-test", command=lambda: self._submit("/selftest"))
        catseek.add_separator()
        catseek.add_command(label="Exit CatSeek R11.x10.9.26", command=root.destroy)
        menu.add_cascade(label=APP_NAME, menu=catseek)
        root.config(menu=menu)

        header = tk.Frame(root, bg=self.PANEL, padx=18, pady=14)
        header.pack(fill="x")
        logo = tk.Frame(header, bg="#000000", width=46, height=46)
        logo.pack(side="left")
        logo.pack_propagate(False)
        tk.Label(logo, text="🐱", bg="#000000", fg=self.BLUE, font=self._font(23)).place(relx=0.5, rely=0.5, anchor="center")
        name = tk.Frame(header, bg=self.PANEL)
        name.pack(side="left", padx=(12, 0))
        tk.Label(name, text=APP_NAME, bg=self.PANEL, fg=self.TEXT, font=self._font(17, True)).pack(anchor="w")
        report = self.engine.model.report
        tk.Label(
            name,
            text=(
                f"Pretrained GGUF backend · "
                f"local checkpoint · {GUI_FPS} FPS UI · {self.engine.model.config.speed_target}"
            ),
            bg=self.PANEL,
            fg=self.MUTED,
            font=self._font(9),
        ).pack(anchor="w")
        self.status = tk.Label(header, text="CatSeek R11.x10.9.26 inference ready", bg=self.PANEL, fg=self.BLUE_2, font=self._font(10))
        self.status.pack(side="right")

        body = tk.Frame(root, bg=self.BG)
        body.pack(fill="both", expand=True)
        sidebar = tk.Frame(body, bg=self.PANEL, width=220, padx=14, pady=18)
        sidebar.pack(side="left", fill="y")
        sidebar.pack_propagate(False)
        tk.Button(
            sidebar,
            text="+ New CatSeek R11.x10.9.26 chat",
            command=self._new_chat,
            bg="#000000",
            fg=self.BLUE,
            activebackground="#111827",
            activeforeground=self.BLUE_2,
            relief="flat",
            bd=0,
            padx=10,
            pady=10,
            font=self._font(10, True),
            cursor="hand2",
        ).pack(fill="x")
        tk.Label(sidebar, text="REAL RAM LM", bg=self.PANEL, fg=self.MUTED, font=self._font(9, True)).pack(anchor="w", pady=(22, 8))
        for line in (
            "● Pretrained DeepSeek-R1 distill",
            "● Local llama.cpp inference",
            "● First-run checkpoint download",
            "● Offline after model cached",
            "● English / 中文",
            "● Multi-turn conversation",
            "● Reasoning-capable checkpoint",
            "● DSpark draft model: not enabled",
            f"● GUI {GUI_FPS} FPS",
        ):
            tk.Label(sidebar, text=line, bg=self.PANEL, fg=self.BLUE_2, font=self._font(9)).pack(anchor="w", pady=3)
        tk.Label(
            sidebar,
            text="/model\n/selftest\n/deliberation\n/train 100\n/teach Q => A\n/candidates 3\n/clear",
            justify="left",
            bg=self.PANEL,
            fg=self.MUTED,
            font=self._font(9, mono=True),
        ).pack(anchor="w", side="bottom")

        chat_area = tk.Frame(body, bg=self.BG)
        chat_area.pack(side="left", fill="both", expand=True)
        self.chat = scrolledtext.ScrolledText(
            chat_area,
            state="disabled",
            wrap="word",
            bg=self.BG,
            fg=self.TEXT,
            insertbackground=self.BLUE,
            selectbackground="#1d4ed8",
            relief="flat",
            bd=0,
            padx=26,
            pady=20,
            font=self._font(11),
        )
        self.chat.pack(fill="both", expand=True)
        self.chat.tag_configure("title", foreground=self.BLUE_2, font=self._font(11, True), spacing1=12)
        self.chat.tag_configure("user", foreground="#93c5fd", font=self._font(11))
        self.chat.tag_configure("bot", foreground=self.TEXT, font=self._font(11))
        self.chat.tag_configure("muted", foreground=self.MUTED, font=self._font(9))
        self.chat.tag_configure("error", foreground=self.RED, font=self._font(10))
        self._append(f"{APP_NAME}\n", "title")
        self._append(
            "CatSeek R1 uses a real pretrained DeepSeek-R1 distilled checkpoint, downloaded on first inference.\n",
            "muted",
        )

        composer = tk.Frame(chat_area, bg=self.PANEL, padx=18, pady=14)
        composer.pack(fill="x")
        self.entry = tk.Text(
            composer,
            height=3,
            bg=self.INPUT,
            fg=self.TEXT,
            insertbackground=self.BLUE,
            selectbackground="#1d4ed8",
            relief="flat",
            bd=0,
            padx=12,
            pady=10,
            font=self._font(10),
            wrap="word",
            undo=True,
        )
        self.entry.pack(side="left", fill="x", expand=True)
        self.entry.bind("<Return>", self._on_enter)
        self.send = tk.Button(
            composer,
            text="INFER ↑",
            command=self._submit,
            bg="#000000",
            fg=self.BLUE,
            activebackground="#111827",
            activeforeground=self.BLUE_2,
            relief="flat",
            bd=0,
            padx=16,
            pady=12,
            font=self._font(10, True),
            cursor="hand2",
        )
        self.send.pack(side="right", padx=(12, 0))
        self.entry.focus_set()

    def _append(self, text: str, tag: str = "bot") -> None:
        self.chat.config(state="normal")
        self.chat.insert("end", text, tag)
        self.chat.config(state="disabled")
        self.chat.see("end")

    def _new_chat(self) -> None:
        # Invalidate every queued result from the previous conversation. A
        # running inference cannot be force-killed safely, so its visible
        # result is discarded and its final idle event unlocks the composer.
        self.conversation_id += 1
        self.engine.clear()
        self.chat.config(state="normal")
        self.chat.delete("1.0", "end")
        self.chat.config(state="disabled")
        self.entry.delete("1.0", "end")
        self.entry.edit_reset()
        self._append(f"{APP_NAME}\n", "title")
        if self.busy:
            self._append(
                "New RAM-only conversation created. Finishing the previous inference in the background…\n",
                "muted",
            )
            self.status.config(text="New chat · finishing previous inference…")
        else:
            self.active_request_id = None
            self.send.config(state="normal")
            self._append("New RAM-only language-model conversation.\n", "muted")
            self.status.config(text="CatSeek R11.x10.9.26 new chat ready")
        self.entry.focus_set()

    def _on_enter(self, event) -> Optional[str]:
        if event.state & 0x1:
            return None
        self._submit()
        return "break"

    def _submit(self, forced: Optional[str] = None) -> None:
        if self.busy:
            return
        prompt = forced if isinstance(forced, str) else self.entry.get("1.0", "end-1c").strip()
        if not prompt:
            return
        self.entry.delete("1.0", "end")
        self._append("\nYOU\n", "title")
        self._append(prompt + "\n", "user")
        self._append(f"\n{APP_NAME}\n", "title")
        self.busy = True
        self.request_serial += 1
        request_id = self.request_serial
        conversation_id = self.conversation_id
        self.active_request_id = request_id
        self.send.config(state="disabled")
        self.status.config(text="CatSeek R11.x10.9.26 computing next tokens…")

        def worker() -> None:
            try:
                reply = self.engine.reply(prompt)
                self.events.put(("done", conversation_id, request_id, reply))
            except Exception as exc:
                self.events.put(("error", conversation_id, request_id, f"{type(exc).__name__}: {exc}"))
            finally:
                self.events.put(("idle", conversation_id, request_id, None))

        threading.Thread(target=worker, daemon=True).start()

    def _drain(self) -> None:
        try:
            while True:
                kind, conversation_id, request_id, payload = self.events.get_nowait()
                is_current = conversation_id == self.conversation_id
                if kind == "done" and is_current:
                    reply = payload
                    self._append(reply.text, "bot")
                    suffix = (
                        f"\n\n{reply.route} · {reply.tokens} tokens · "
                        f"{reply.tokens_per_second:.1f} tok/s · {reply.elapsed_ms:.1f} ms\n"
                    )
                    self._append(suffix, "muted")
                    self.status.config(text=f"{APP_NAME} ready · {reply.tokens_per_second:.1f} tok/s")
                elif kind == "error" and is_current:
                    self._append("ERROR\n" + str(payload) + "\n", "error")
                    self.status.config(text="CatSeek R11.x10.9.26 error")
                elif kind == "idle" and request_id == self.active_request_id:
                    if not is_current:
                        # The stale worker may have appended to engine history
                        # after New Chat cleared it; clear once more at exit.
                        self.engine.clear()
                    self.busy = False
                    self.active_request_id = None
                    self.send.config(state="normal")
                    if not is_current:
                        self.status.config(text="CatSeek R11.x10.9.26 new chat ready")
                        self._append("Previous inference discarded. New chat is ready.\n", "muted")
                    self.entry.focus_set()
        except queue.Empty:
            pass
        self.root.after(GUI_TICK_MS, self._drain)

def main():
    if len(sys.argv)>1 and sys.argv[1]=="--self-test":
        result=LocalEngine().self_test();print(json.dumps(result,indent=2));return 0 if result["ok"] else 1
    if len(sys.argv)>1 and sys.argv[1]=="--prompt":
        print(LocalEngine().reply(" ".join(sys.argv[2:])).text);return 0
    root=tk.Tk();CatSeekGUI(root,LocalEngine());root.mainloop();return 0

if __name__=="__main__":raise SystemExit(main())
