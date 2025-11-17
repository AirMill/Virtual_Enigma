#!/usr/bin/env python3
"""
enigma_gui.py
A complete Enigma I simulation with GUI (tkinter).
Supports rotors I-V, Reflector B, plugboard, ring settings, double-stepping,
and an import/export compact message format for sharing settings + ciphertext.
"""

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import string

ALPHABET = string.ascii_uppercase

# Rotor wirings and notches for common historical rotors (mapped A->0 ... Z->25)
ROTOR_SPECS = {
    # wiring (as letters) , notch positions (letters where rotor causes next to step)
    "I":   ("EKMFLGDQVZNTOWYHXUSPAIBRCJ", "Q"),
    "II":  ("AJDKSIRUXBLHWTMCQGZNPYFVOE", "E"),
    "III": ("BDFHJLCPRTXVZNYEIWGAKMUSQO", "V"),
    "IV":  ("ESOVPZJAYQUIRHXLNFTGKDCMWB", "J"),
    "V":   ("VZBRGITYUPSDNHLXAWMJQOFECK", "Z"),
    # optionally you can add more rotors here
}

REFLECTORS = {
    "B": "YRUHQSLDPXNGOKMIEBFZCWVJAT",
    # Add reflector C etc. if desired
}

def letter_to_index(c):
    return ord(c) - ord('A')

def index_to_letter(i):
    return ALPHABET[i % 26]

class Rotor:
    def __init__(self, name, wiring_str, notch_letters, ring_setting=1, position='A'):
        self.name = name
        self.wiring = [letter_to_index(c) for c in wiring_str]
        # inverse wiring for backward pass
        self.inverse_wiring = [0]*26
        for i, w in enumerate(self.wiring):
            self.inverse_wiring[w] = i
        self.notches = set(letter_to_index(c) for c in notch_letters)
        # ring setting: 1..26 (1 means no offset). internally we store 0..25 offset
        self.ring = (ring_setting - 1) % 26
        self.position = letter_to_index(position)

    def step(self):
        self.position = (self.position + 1) % 26

    def at_notch(self):
        # notch is evaluated with current position (window letter)
        return self.position in self.notches

    def forward(self, c):  # c is 0..25 entering rotor right->left
        # apply rotor considering ring and position
        shifted = (c + self.position - self.ring) % 26
        wired = self.wiring[shifted]
        out = (wired - self.position + self.ring) % 26
        return out

    def backward(self, c):  # c is 0..25 entering rotor left->right
        shifted = (c + self.position - self.ring) % 26
        wired = self.inverse_wiring[shifted]
        out = (wired - self.position + self.ring) % 26
        return out

class Reflector:
    def __init__(self, wiring_str):
        self.wiring = [letter_to_index(c) for c in wiring_str]

    def reflect(self, c):
        return self.wiring[c]

class Plugboard:
    def __init__(self, pairs=None):
        # pairs: list of 2-letter strings e.g. ["AB","CD"]
        self.mapping = list(range(26))
        if pairs:
            for p in pairs:
                a = letter_to_index(p[0])
                b = letter_to_index(p[1])
                self.mapping[a] = b
                self.mapping[b] = a

    def swap(self, c):
        return self.mapping[c]

class EnigmaMachine:
    def __init__(self, rotor_names, rotor_positions, ring_settings, reflector_name, plug_pairs):
        # rotor_names: list of 3 rotor names, left-to-right e.g. ["I","II","III"]
        # rotor_positions: list of letters for starting positions left-to-right e.g. ['A','A','A']
        # ring_settings: list of ints 1..26 left-to-right e.g. [1,1,1]
        self.rotors = []
        for name, pos, ring in zip(rotor_names, rotor_positions, ring_settings):
            wiring, notch = ROTOR_SPECS[name]
            self.rotors.append(Rotor(name, wiring, notch, ring_setting=ring, position=pos))
        self.reflector = Reflector(REFLECTORS[reflector_name])
        self.plugboard = Plugboard(plug_pairs)

    def step_rotors(self):
        # Implement classic Enigma stepping with double-step:
        # If middle rotor is at notch -> left rotor steps (because middle will step)
        # If right rotor is at notch -> middle rotor steps
        # Finally right rotor always steps
        left, middle, right = self.rotors[0], self.rotors[1], self.rotors[2]
        # Check double-step conditions before stepping right
        middle_will_step = right.at_notch() or middle.at_notch()
        if middle_will_step:
            middle.step()
        if middle.at_notch():  # if middle was at notch before stepping, after stepping it triggers left
            left.step()
        # finally right always steps
        right.step()

    def process_character(self, ch):
        if ch not in ALPHABET:
            return ch
        self.step_rotors()
        c = letter_to_index(ch)
        # plugboard in
        c = self.plugboard.swap(c)
        # pass through rotors right->left
        for rotor in reversed(self.rotors):
            c = rotor.forward(c)
        # reflector
        c = self.reflector.reflect(c)
        # back through rotors left->right
        for rotor in self.rotors:
            c = rotor.backward(c)
        # plugboard out
        c = self.plugboard.swap(c)
        return index_to_letter(c)

    def encrypt(self, text):
        result = []
        for ch in text.upper():
            if ch in ALPHABET:
                result.append(self.process_character(ch))
            else:
                # keep spaces/punctuation as-is
                result.append(ch)
        return ''.join(result)

    def get_settings_serialized(self):
        # Return compact settings string for embedding with ciphertext
        # rotor names left->right, positions, ring settings, reflector, plugboard pairs
        rotor_names = ','.join(r.name for r in self.rotors)
        positions = ''.join(index_to_letter(r.position) for r in self.rotors)
        rings = ','.join(f"{(r.ring+1):02d}" for r in self.rotors)
        reflector = 'B'  # only B supported in this script; could be made dynamic
        # plugboard pairs
        pairs = []
        used = set()
        for i, m in enumerate(self.plugboard.mapping):
            if i < m and m != i:
                pairs.append(index_to_letter(i) + '-' + index_to_letter(m))
        plugstr = '|'.join(pairs)
        return f"R:{rotor_names};POS:{positions};RING:{rings};REF:{reflector};PLUG:{plugstr}"

    @classmethod
    def from_serialized(cls, serialized):
        # Parse string produced by get_settings_serialized
        # Example: R:I,II,III;POS:ABC;RING:01,01,01;REF:B;PLUG:AT-BS|CM
        parts = {}
        for part in serialized.split(';'):
            if ':' in part:
                k, v = part.split(':', 1)
                parts[k] = v
        rotor_names = parts.get('R', 'I,II,III').split(',')
        positions = list(parts.get('POS', 'AAA'))
        rings = [int(x) for x in parts.get('RING', '01,01,01').split(',')]
        reflector = parts.get('REF', 'B')
        plugpairs = []
        plug_raw = parts.get('PLUG', '')
        if plug_raw:
            # plug pairs separated by '|' or '-' pattern: allow both "AB-CD" or "A-B|C-D"
            if '|' in plug_raw:
                items = plug_raw.split('|')
            else:
                items = plug_raw.split('-')
                # may be not ideal; prefer 'A-B|C-D'
                # if parsed as pieces of hyphen, try to rebuild pairs in twos
                if len(items) > 2 and len(items)%2==0:
                    rebuilt = []
                    for i in range(0, len(items), 2):
                        rebuilt.append(items[i] + items[i+1])
                    items = rebuilt
            for it in items:
                if '-' in it:
                    a,b = it.split('-')
                    plugpairs.append(a.strip()+b.strip())
                elif len(it)==2:
                    plugpairs.append(it.strip())
        return cls(rotor_names, positions, rings, reflector, plugpairs)

# ---------- GUI code using tkinter ----------
class EnigmaGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Enigma Simulator")
        # State
        self.available_rotors = list(ROTOR_SPECS.keys())
        self.reflectors = list(REFLECTORS.keys())
        # defaults
        self.left_rotor_var = tk.StringVar(value="I")
        self.middle_rotor_var = tk.StringVar(value="II")
        self.right_rotor_var = tk.StringVar(value="III")
        self.left_pos_var = tk.StringVar(value="A")
        self.mid_pos_var = tk.StringVar(value="A")
        self.right_pos_var = tk.StringVar(value="A")
        self.left_ring_var = tk.IntVar(value=1)
        self.mid_ring_var = tk.IntVar(value=1)
        self.right_ring_var = tk.IntVar(value=1)
        self.reflector_var = tk.StringVar(value=self.reflectors[0])
        self.plugboard_var = tk.StringVar(value="")  # e.g. "AT BS CM"

        self.create_widgets()

    def create_widgets(self):
        frm = ttk.Frame(self.root, padding=8)
        frm.grid(row=0, column=0, sticky="nsew")

        # Rotor selection and settings
        rotor_frame = ttk.LabelFrame(frm, text="Rotors (left → right)")
        rotor_frame.grid(row=0, column=0, sticky="ew", padx=4, pady=4)

        # Left rotor
        ttk.Label(rotor_frame, text="Left").grid(row=0, column=0)
        ttk.OptionMenu(rotor_frame, self.left_rotor_var, self.left_rotor_var.get(), *self.available_rotors).grid(row=1, column=0)
        ttk.Entry(rotor_frame, width=3, textvariable=self.left_pos_var).grid(row=2, column=0)
        ttk.Spinbox(rotor_frame, from_=1, to=26, width=4, textvariable=self.left_ring_var).grid(row=3, column=0)

        # Middle rotor
        ttk.Label(rotor_frame, text="Middle").grid(row=0, column=1)
        ttk.OptionMenu(rotor_frame, self.middle_rotor_var, self.middle_rotor_var.get(), *self.available_rotors).grid(row=1, column=1)
        ttk.Entry(rotor_frame, width=3, textvariable=self.mid_pos_var).grid(row=2, column=1)
        ttk.Spinbox(rotor_frame, from_=1, to=26, width=4, textvariable=self.mid_ring_var).grid(row=3, column=1)

        # Right rotor
        ttk.Label(rotor_frame, text="Right").grid(row=0, column=2)
        ttk.OptionMenu(rotor_frame, self.right_rotor_var, self.right_rotor_var.get(), *self.available_rotors).grid(row=1, column=2)
        ttk.Entry(rotor_frame, width=3, textvariable=self.right_pos_var).grid(row=2, column=2)
        ttk.Spinbox(rotor_frame, from_=1, to=26, width=4, textvariable=self.right_ring_var).grid(row=3, column=2)

        # Reflector and plugboard
        config_frame = ttk.Frame(frm)
        config_frame.grid(row=1, column=0, sticky="ew", pady=(4,0))
        ttk.Label(config_frame, text="Reflector").grid(row=0, column=0, sticky="w")
        ttk.OptionMenu(config_frame, self.reflector_var, self.reflector_var.get(), *self.reflectors).grid(row=0, column=1, sticky="w")
        ttk.Label(config_frame, text="Plugboard pairs (space or comma separated, e.g. AT BS CM)").grid(row=1, column=0, columnspan=2, sticky="w")
        ttk.Entry(config_frame, width=40, textvariable=self.plugboard_var).grid(row=2, column=0, columnspan=2, sticky="w")

        # Input/Output text
        io_frame = ttk.LabelFrame(frm, text="Input / Output")
        io_frame.grid(row=2, column=0, sticky="nsew", pady=6)
        self.input_text = tk.Text(io_frame, height=8, width=60)
        self.input_text.grid(row=0, column=0, padx=4, pady=4)
        self.output_text = tk.Text(io_frame, height=8, width=60)
        self.output_text.grid(row=1, column=0, padx=4, pady=4)

        # Buttons
        btn_frame = ttk.Frame(frm)
        btn_frame.grid(row=3, column=0, sticky="ew")
        ttk.Button(btn_frame, text="Encrypt/Decrypt", command=self.encrypt_action).grid(row=0, column=0, padx=4)
        ttk.Button(btn_frame, text="Clear", command=self.clear_action).grid(row=0, column=1, padx=4)
        ttk.Button(btn_frame, text="Export (share)", command=self.export_action).grid(row=0, column=2, padx=4)
        ttk.Button(btn_frame, text="Import (paste settings+cipher)", command=self.import_action).grid(row=0, column=3, padx=4)
        ttk.Button(btn_frame, text="Randomize positions", command=self.randomize_positions).grid(row=0, column=4, padx=4)
        ttk.Button(btn_frame, text="Test roundtrip", command=self.test_roundtrip).grid(row=0, column=5, padx=4)

        # status
        self.status_var = tk.StringVar(value="Ready")
        ttk.Label(frm, textvariable=self.status_var).grid(row=4, column=0, sticky="w", pady=(6,0))

    def parse_plug_pairs(self, txt):
        # Accept "AT BS CM" or "A-T,B-S" etc. Return list of 2-letter strings like ["AT","BS"]
        txt = txt.strip().upper()
        if not txt:
            return []
        # normalize separators
        for sep in [',', ';', '/']:
            txt = txt.replace(sep, ' ')
        parts = [p.strip() for p in txt.split() if p.strip()]
        pairs = []
        for p in parts:
            p = p.replace('-', '')
            if len(p) == 2 and p[0] != p[1]:
                pairs.append(p)
        # remove duplicates/conflicts (simple approach)
        used = set()
        clean = []
        for p in pairs:
            a, b = p[0], p[1]
            if a in used or b in used:
                continue
            clean.append(p)
            used.add(a); used.add(b)
        return clean

    def build_machine_from_ui(self):
        rotor_names = [self.left_rotor_var.get(), self.middle_rotor_var.get(), self.right_rotor_var.get()]
        positions = [self.left_pos_var.get().upper()[:1] or 'A', self.mid_pos_var.get().upper()[:1] or 'A', self.right_pos_var.get().upper()[:1] or 'A']
        try:
            rings = [int(self.left_ring_var.get()), int(self.mid_ring_var.get()), int(self.right_ring_var.get())]
        except Exception:
            messagebox.showerror("Error", "Ring settings must be integers 1..26")
            raise
        reflector = self.reflector_var.get()
        plugs = self.parse_plug_pairs(self.plugboard_var.get())
        return EnigmaMachine(rotor_names, positions, rings, reflector, plugs)

    def encrypt_action(self):
        try:
            machine = self.build_machine_from_ui()
        except Exception:
            return
        input_text = self.input_text.get("1.0", tk.END).strip('\n')
        out = machine.encrypt(input_text)
        self.output_text.delete("1.0", tk.END)
        self.output_text.insert(tk.END, out)
        self.status_var.set("Encrypted/Decrypted. Rotors advanced accordingly.")

    def clear_action(self):
        self.input_text.delete("1.0", tk.END)
        self.output_text.delete("1.0", tk.END)
        self.status_var.set("Cleared")

    def export_action(self):
        # Create machine then serialize settings and include ciphertext
        try:
            machine = self.build_machine_from_ui()
        except Exception:
            return
        ct = self.output_text.get("1.0", tk.END).strip().replace('\n', '')
        if not ct:
            messagebox.showinfo("Nothing to export", "Run Encrypt/Decrypt first to create ciphertext.")
            return
        settings = machine.get_settings_serialized()
        full = f"ENIGMA|{settings}|CT:{ct}"
        # show in dialog for easy copy/paste
        dlg = tk.Toplevel(self.root)
        dlg.title("Exported settings+ciphertext (copy and send this whole text)")
        tk.Text(dlg, height=6, width=80).pack(padx=8, pady=8)
        t = dlg.children[list(dlg.children.keys())[-1]]
        t.insert(tk.END, full)
        t.configure(state='disabled')
        ttk.Button(dlg, text="Close", command=dlg.destroy).pack(pady=(0,8))
        self.status_var.set("Export string created (copy and send).")

    def import_action(self):
        s = simpledialog.askstring("Import", "Paste the exported settings+ciphertext string here:")
        if not s:
            return
        s = s.strip()
        if not s.startswith("ENIGMA|"):
            messagebox.showerror("Invalid format", "String must start with 'ENIGMA|'")
            return
        payload = s[len("ENIGMA|"):]
        # split off CT:
        if "|CT:" in payload:
            settings_part, ct_part = payload.split("|CT:", 1)
        elif ";CT:" in payload:
            settings_part, ct_part = payload.split(";CT:", 1)
        else:
            # attempt to find CT:
            idx = payload.find("CT:")
            if idx==-1:
                messagebox.showerror("Invalid", "No ciphertext part found")
                return
            settings_part = payload[:idx].rstrip('|;')
            ct_part = payload[idx+3:]
        # settings part might use ; separators; replace '|' with ';' for parser
        settings_part = settings_part.replace('|',';')
        # create machine
        try:
            machine = EnigmaMachine.from_serialized(settings_part)
        except Exception as e:
            messagebox.showerror("Parse error", f"Failed to parse settings: {e}")
            return
        # update UI fields to reflect imported machine
        # rotor names
        for i, r in enumerate(machine.rotors):
            if i==0:
                self.left_rotor_var.set(r.name); self.left_pos_var.set(index_to_letter(r.position)); self.left_ring_var.set(r.ring+1)
            elif i==1:
                self.middle_rotor_var.set(r.name); self.mid_pos_var.set(index_to_letter(r.position)); self.mid_ring_var.set(r.ring+1)
            else:
                self.right_rotor_var.set(r.name); self.right_pos_var.set(index_to_letter(r.position)); self.right_ring_var.set(r.ring+1)
        self.reflector_var.set('B')
        # plugboard reconstruct string
        pairs = []
        used = set()
        for i, m in enumerate(machine.plugboard.mapping):
            if i < m and m != i:
                pairs.append(index_to_letter(i)+index_to_letter(m))
        self.plugboard_var.set(' '.join(pairs))
        # populate input box with ciphertext
        self.input_text.delete("1.0", tk.END)
        self.input_text.insert(tk.END, ct_part.strip())
        self.output_text.delete("1.0", tk.END)
        self.status_var.set("Imported settings and ciphertext. Press Encrypt/Decrypt to decode.")

    def randomize_positions(self):
        import random
        self.left_pos_var.set(random.choice(ALPHABET))
        self.mid_pos_var.set(random.choice(ALPHABET))
        self.right_pos_var.set(random.choice(ALPHABET))
        self.status_var.set("Randomized rotor window positions")

    def test_roundtrip(self):
        # Simple sanity test: encrypt then reset positions and decrypt
        try:
            initial_machine = self.build_machine_from_ui()
        except Exception:
            return
        pt = "HELLO WORLD"
        machine_enc = self.build_machine_from_ui()
        ct = machine_enc.encrypt(pt)
        # To decrypt we must reset rotors to same starting positions: build new machine with same UI values (positions unchanged)
        machine_dec = self.build_machine_from_ui()
        # For a correct Enigma, encrypting ct with same start positions yields original plaintext (since machine is reciprocal)
        out = machine_dec.encrypt(ct)
        if out.replace(' ','') == pt.replace(' ',''):
            messagebox.showinfo("Roundtrip OK", f"Roundtrip succeeded.\nPlain: {pt}\nCipher: {ct}\nDecipher: {out}")
        else:
            messagebox.showwarning("Roundtrip failed", f"Roundtrip mismatch.\nPlain: {pt}\nCipher: {ct}\nDecipher: {out}")

def main():
    root = tk.Tk()
    app = EnigmaGUI(root)
    root.mainloop()

if __name__ == "__main__":
    main()
