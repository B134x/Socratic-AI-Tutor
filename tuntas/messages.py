"""Tutor messages in English and Bahasa Indonesia.

Templates may show the question's numbers but never the answer. tutor.py relies on
this: an AI rewrite may not add any number the template lacks.
"""

from __future__ import annotations

from .graph import LABELS

LANGUAGES = ("en", "id")

STEP_LABELS = {
    "en": {
        "diagnose": "Prerequisite check", "remediate": "Short review", "gate1": "Gate 1: new numbers",
        "factor": "Write the factor form", "gate2": "Gate 2: factor a new one", "roots": "Find the roots",
        "transfer": "Transfer problem", "done": "Done",
    },
    "id": {
        "diagnose": "Cek prasyarat", "remediate": "Ulasan singkat", "gate1": "Gerbang 1: angka baru",
        "factor": "Tulis bentuk faktor", "gate2": "Gerbang 2: faktorkan soal baru", "roots": "Cari akar-akarnya",
        "transfer": "Soal transfer", "done": "Selesai",
    },
}

TEMPLATES = {
    "en": {
        "start_diagnose": "Before we factor {poly}, a quick check on what you need for it.",
        "start_skip": "Your earlier work shows you already handle {concept}, so we start with the factor form.",
        "prompt_pair": "Find two whole numbers whose product is {product} and whose sum is {total}. Type them like 4, -1.",
        "prompt_factor": "Write {poly} as a product of two brackets, for example (x + a)(x + b).",
        "prompt_gate2": "Now factor {poly} on your own.",
        "prompt_roots": "{factored} = 0. Which values of x make this product zero? Type both, like 2, 5.",
        "prompt_transfer": "A new problem to finish: solve {poly} = 0. Give both values of x.",
        "pair_correct": "Correct.",
        "pair_wrong": "Not yet: {a} × {b} = {got_product} and {a} + {b} = {got_sum}. You need product {product} and sum {total}.",
        "pair_not_an_answer": "I can only check two whole numbers separated by a comma, like 4, -1. Nothing was scored.",
        "expression_not_an_answer": "I could not read that as an expression in x. Try something like (x + 1)(x - 4). Nothing was scored.",
        "factor_correct": "Correct form.",
        "factor_not_factored": "That is the same expression, but it is not written as a product of two brackets yet.",
        "factor_wrong": "That does not expand back to {poly}. Expand your brackets to check.",
        "roots_correct": "Correct.",
        "roots_wrong": "Not yet. Check each bracket: which x makes it equal to zero?",
        "roots_not_an_answer": "Type the two values of x, like 2, 5. Nothing was scored.",
        "remediate_both_negative": "Signs first: a negative times a negative is positive, and adding two negatives gives a negative. So two negative numbers can have a positive product and a negative sum.",
        "remediate_both_positive": "List the pairs of whole numbers that multiply to the product, then check which pair adds up to the sum.",
        "remediate_mixed": "A negative product means the two numbers have opposite signs. The number with the larger size carries the sign of the sum.",
        "remediate_zero": "If the product is 0, one of the numbers must be 0. The other one is then the sum.",
        "remediate_factoring": "(x + a)(x + b) expands to x² + (a + b)x + ab. So a and b multiply to the last number and add up to the number in front of x.",
        "mastery_change": "Mastery of {concept}: {before} → {after}.",
        "gate_open": "The gate is open.",
        "one_more": "One more with new numbers.",
        "aided_not_scored": "Correct, but a hint was used, so this one is not scored. Here is a fresh one to do on your own.",
        "cap_reached": "Let's slow down with a short review. Your teacher has been notified so they can help.",
        "done": "Done. You solved it yourself. Hints used along the way: {hints}.",
        "done_flagged": "We'll stop here for today. Your teacher can see where you got stuck and will help with the next step.",
        "hint_pair_1": "Which pairs of whole numbers multiply to {product}?",
        "hint_pair_2": "Of those pairs, which one adds up to {total}?",
        "hint_pair_3": "Check the signs: what must they be for product {product} and sum {total}?",
        "hint_factor_1": "A product of two brackets looks like (x + a)(x + b).",
        "hint_factor_2": "a × b must be {c} and a + b must be {b}.",
        "hint_factor_3": "Expand your answer and compare it with {poly}.",
        "hint_roots_1": "A product is zero when one of its factors is zero.",
        "hint_roots_2": "Set each bracket equal to zero.",
        "hint_roots_3": "Solve each small equation for x.",
        "hint_transfer_1": "Find two numbers with product {c} and sum {b} first.",
        "hint_transfer_2": "Use them to write the factor form.",
        "hint_transfer_3": "Then set each bracket equal to zero.",
        "hints_exhausted": "No more hints for this step. Try an answer: a wrong one still shows us where to look next.",
        "no_hints_here": "This step has no hints. Read it, then continue.",
    },
    "id": {
        "start_diagnose": "Sebelum memfaktorkan {poly}, kita cek dulu bekal yang kamu perlukan.",
        "start_skip": "Hasil belajarmu sebelumnya menunjukkan kamu sudah menguasai {concept}, jadi kita mulai dari bentuk faktor.",
        "prompt_pair": "Cari dua bilangan bulat yang hasil kalinya {product} dan jumlahnya {total}. Tulis seperti 4, -1.",
        "prompt_factor": "Tulis {poly} sebagai perkalian dua kurung, misalnya (x + a)(x + b).",
        "prompt_gate2": "Sekarang faktorkan {poly} sendiri.",
        "prompt_roots": "{factored} = 0. Nilai x berapa yang membuat hasil kali ini nol? Tulis keduanya, seperti 2, 5.",
        "prompt_transfer": "Soal baru sebagai penutup: selesaikan {poly} = 0. Tulis kedua nilai x.",
        "pair_correct": "Benar.",
        "pair_wrong": "Belum tepat: {a} × {b} = {got_product} dan {a} + {b} = {got_sum}. Yang dicari hasil kali {product} dan jumlah {total}.",
        "pair_not_an_answer": "Aku hanya bisa memeriksa dua bilangan bulat yang dipisah koma, seperti 4, -1. Tidak ada nilai yang dicatat.",
        "expression_not_an_answer": "Aku tidak bisa membacanya sebagai bentuk aljabar dalam x. Coba seperti (x + 1)(x - 4). Tidak ada nilai yang dicatat.",
        "factor_correct": "Bentuknya benar.",
        "factor_not_factored": "Itu bentuk yang sama, tetapi belum ditulis sebagai perkalian dua kurung.",
        "factor_wrong": "Jika dijabarkan, hasilnya bukan {poly}. Coba jabarkan kurungmu untuk memeriksa.",
        "roots_correct": "Benar.",
        "roots_wrong": "Belum tepat. Periksa tiap kurung: x berapa yang membuatnya bernilai nol?",
        "roots_not_an_answer": "Tulis kedua nilai x, seperti 2, 5. Tidak ada nilai yang dicatat.",
        "remediate_both_negative": "Tanda dulu: negatif dikali negatif hasilnya positif, dan negatif ditambah negatif hasilnya negatif. Jadi dua bilangan negatif bisa punya hasil kali positif dan jumlah negatif.",
        "remediate_both_positive": "Daftar pasangan bilangan bulat yang hasil kalinya sama dengan angka itu, lalu cek pasangan mana yang jumlahnya cocok.",
        "remediate_mixed": "Hasil kali negatif berarti kedua bilangan berbeda tanda. Bilangan yang nilai mutlaknya lebih besar mengikuti tanda jumlahnya.",
        "remediate_zero": "Jika hasil kalinya 0, salah satu bilangan pasti 0. Bilangan lainnya sama dengan jumlahnya.",
        "remediate_factoring": "(x + a)(x + b) jika dijabarkan menjadi x² + (a + b)x + ab. Jadi a dan b dikalikan menjadi angka terakhir dan dijumlahkan menjadi angka di depan x.",
        "mastery_change": "Penguasaan {concept}: {before} → {after}.",
        "gate_open": "Gerbang terbuka.",
        "one_more": "Satu soal lagi dengan angka baru.",
        "aided_not_scored": "Benar, tetapi kamu memakai petunjuk, jadi soal ini tidak dinilai. Ini soal baru untuk dikerjakan sendiri.",
        "cap_reached": "Kita pelan-pelan dulu dengan ulasan singkat. Gurumu sudah diberi tahu agar bisa membantu.",
        "done": "Selesai. Kamu menyelesaikannya sendiri. Petunjuk yang dipakai: {hints}.",
        "done_flagged": "Kita berhenti di sini dulu hari ini. Gurumu bisa melihat bagian yang sulit dan akan membantu langkah berikutnya.",
        "hint_pair_1": "Pasangan bilangan bulat mana saja yang hasil kalinya {product}?",
        "hint_pair_2": "Dari pasangan itu, mana yang jumlahnya {total}?",
        "hint_pair_3": "Perhatikan tandanya: harus bertanda apa agar hasil kalinya {product} dan jumlahnya {total}?",
        "hint_factor_1": "Perkalian dua kurung bentuknya (x + a)(x + b).",
        "hint_factor_2": "a × b harus {c} dan a + b harus {b}.",
        "hint_factor_3": "Jabarkan jawabanmu lalu bandingkan dengan {poly}.",
        "hint_roots_1": "Hasil kali bernilai nol jika salah satu faktornya nol.",
        "hint_roots_2": "Samakan setiap kurung dengan nol.",
        "hint_roots_3": "Selesaikan setiap persamaan kecil itu untuk x.",
        "hint_transfer_1": "Cari dulu dua bilangan dengan hasil kali {c} dan jumlah {b}.",
        "hint_transfer_2": "Gunakan keduanya untuk menulis bentuk faktor.",
        "hint_transfer_3": "Lalu samakan setiap kurung dengan nol.",
        "hints_exhausted": "Petunjuk untuk langkah ini sudah habis. Coba jawab saja: jawaban yang salah tetap menunjukkan bagian yang perlu dilihat.",
        "no_hints_here": "Langkah ini tidak punya petunjuk. Baca, lalu lanjutkan.",
    },
}


def decimal(lang: str, value: float) -> str:
    """Two decimals, with the decimal comma Indonesian schools use."""
    text = f"{value:.2f}"
    return text.replace(".", ",") if lang == "id" else text


def render(lang: str, key: str, args: dict | None = None) -> str:
    lang = lang if lang in LANGUAGES else "en"
    args = dict(args or {})
    if "concept" in args:
        args["concept"] = LABELS[lang].get(args["concept"], args["concept"]).lower()
    for name, value in args.items():
        if isinstance(value, float):
            args[name] = decimal(lang, value)
        elif key == "pair_wrong" and name in ("a", "b") and isinstance(value, int) and value < 0:
            args[name] = f"({value})"  # 2 × (-4), not 2 × -4
    return TEMPLATES[lang][key].format(**args)
