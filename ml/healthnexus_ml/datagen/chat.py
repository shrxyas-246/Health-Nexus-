"""Training corpus for model 1 — the general health-guidance assistant.

Each intent carries the way real patients actually type: fragments, no
punctuation, transliterated Hindi-English ("kitna paani"), typos. The generator
expands the seed phrasings with prefixes, suffixes and light character noise so
the classifier learns the intent rather than one canonical sentence.

Every intent is tagged with an urgency level, which trains the second head:

* ``routine``     — safe to answer directly.
* ``see_doctor``  — answer, but tell them to get it looked at.
* ``emergency``   — do not answer the question at all; send them to emergency care.

The emergency head is the safety-critical one, so it is evaluated on recall, and
a deterministic red-flag phrase list runs *in front of* the model at serving time
(``models/triage.py``). A classifier that is 98% right is not good enough on its
own when the 2% is chest pain.
"""

from __future__ import annotations

import numpy as np

ROUTINE, SEE_DOCTOR, EMERGENCY = "routine", "see_doctor", "emergency"

# intent -> (urgency, seed phrasings)
INTENTS: dict[str, tuple[str, list[str]]] = {
    "hydration": (ROUTINE, [
        "how much water should i drink",
        "how many litres of water a day",
        "am i drinking enough water",
        "is 2 litres of water enough",
        "kitna paani peena chahiye",
        "water intake per day",
        "should i drink more water in summer",
        "does tea count as water intake",
        "how much water while exercising",
        "signs of dehydration",
        "is it bad to drink too much water",
        "best time to drink water",
    ]),
    "sleep": (ROUTINE, [
        "how many hours of sleep do i need",
        "i am not sleeping well",
        "tips for better sleep",
        "is 6 hours of sleep enough",
        "why do i wake up tired",
        "how to fix my sleep schedule",
        "does screen time affect sleep",
        "should i nap during the day",
        "neend nahi aati kya karu",
        "best bedtime routine",
        "is it bad to sleep late",
        "i wake up in the middle of the night",
        "i cannot stay asleep through the night",
        "i keep getting up at odd hours at night",
        "insomnia every night",
        "takes me two hours to fall asleep",
        "raat ko baar baar neend khulti hai",
    ]),
    "diet_general": (ROUTINE, [
        "what should i eat to stay healthy",
        "is my diet balanced",
        "how much protein do i need",
        "are eggs good for me",
        "should i cut carbs",
        "healthy breakfast ideas",
        "how many calories should i eat a day",
        "is fruit juice healthy",
        "how much salt is too much",
        "what to eat before a workout",
        "is intermittent fasting safe",
        "kya khana chahiye healthy rehne ke liye",
        "is white rice worse than brown rice",
        "which cooking oil is healthiest",
        "should i eat more fibre",
        "are millets better than wheat",
        "is curd good to have daily",
        "how many chapatis should i eat",
        "is paneer or chicken better protein",
        "should i drink milk at night",
    ]),
    "exercise": (ROUTINE, [
        "how much should i exercise",
        "how many steps a day",
        "is walking enough exercise",
        "best exercise for beginners",
        "how often should i go to the gym",
        "can i work out every day",
        "how long should a workout be",
        "exercise for belly fat",
        "is yoga good exercise",
        "should i do cardio or weights",
        "workout kitna karna chahiye",
        "can i use the stairs instead of the gym",
        "is climbing stairs good enough",
        "no time for gym what else can i do",
        "is cycling to work enough activity",
        "how many rest days in a week",
        "should i stretch before or after",
    ]),
    "weight_bmi": (ROUTINE, [
        "what is my ideal weight",
        "what does bmi mean",
        "how do i calculate bmi",
        "am i overweight",
        "how to lose weight safely",
        "how fast can i lose weight",
        "how do i gain weight healthily",
        "is my bmi normal",
        "weight kaise kam kare",
        "why am i not losing weight",
    ]),
    "medication_missed_dose": (ROUTINE, [
        "i missed my medicine dose",
        "what if i forget a tablet",
        "i forgot to take my tablet this morning",
        "should i take a double dose if i missed one",
        "missed my evening medicine what now",
        "i skipped my medicine yesterday",
        "dawai lena bhool gaya",
        "can i take my missed dose now",
    ]),
    "medication_timing": (ROUTINE, [
        "should i take my medicine before or after food",
        "what time should i take my tablet",
        "can i take my medicines together",
        "does this tablet go with milk",
        "how long should i continue the medicine",
        "can i stop my medicine once i feel better",
        "khali pet dawai leni hai kya",
        "morning or night for this tablet",
    ]),
    "medication_side_effect": (SEE_DOCTOR, [
        "my medicine is giving me side effects",
        "i feel nauseous after taking the tablet",
        "this medicine makes me dizzy",
        "i got a rash after starting the new medicine",
        "the tablet upsets my stomach",
        "side effects of my prescription",
        "dawai ke baad chakkar aa raha hai",
        "i feel weak since starting this medicine",
        "ever since the new tablet i feel unwell",
        "started a new medicine and now i feel off",
        "is this reaction because of my new prescription",
        "the new drug is not suiting me",
        "i feel sick every time i take it",
    ]),
    "fever": (SEE_DOCTOR, [
        "i have a fever",
        "my temperature is 101",
        "fever for three days now",
        "what should i do for fever",
        "is 99 degrees a fever",
        "fever with body ache",
        "bukhar hai kya karu",
        "child has fever what to do",
        "should i take paracetamol for fever",
        "temperature is 100 since last evening",
        "running a temperature of 102",
        "mild temperature since morning",
        "shivering and feeling hot",
        "fever comes back every night",
    ]),
    "headache": (SEE_DOCTOR, [
        "i have a headache",
        "constant headache for two days",
        "migraine is back",
        "headache behind my eyes",
        "sir dard ho raha hai",
        "what causes frequent headaches",
        "headache after screen time",
        "dull pain in my head since morning",
        "throbbing pain on one side of my head",
        "my head has been aching all day",
        "pressure in my forehead",
        "headache when i skip meals",
        "head pain with nausea and light sensitivity",
    ]),
    "cold_cough": (ROUTINE, [
        "i have a cold",
        "runny nose and sneezing",
        "cough for a week",
        "sore throat remedies",
        "khansi ho rahi hai",
        "blocked nose what to do",
        "is my cough viral",
    ]),
    "stomach": (SEE_DOCTOR, [
        "stomach ache since morning",
        "i have loose motions",
        "acidity after meals",
        "constipation for three days",
        "pet dard ho raha hai",
        "feeling bloated all the time",
        "vomiting since last night",
        "what to eat during diarrhoea",
    ]),
    "diabetes": (ROUTINE, [
        "what is a normal blood sugar level",
        "my sugar is 180 after food",
        "what is hba1c",
        "can diabetics eat rice",
        "how often should i check my sugar",
        "sugar kaise control kare",
        "diet for diabetes",
        "does exercise lower blood sugar",
        "is fruit ok for diabetics",
    ]),
    "blood_pressure": (ROUTINE, [
        "what is normal blood pressure",
        "my bp is 150 over 95",
        "how to lower blood pressure naturally",
        "how much salt if i have high bp",
        "bp high rehta hai kya karu",
        "should i check bp daily",
        "does stress raise blood pressure",
        "reading came 150 over 100 today",
        "my systolic is always above 140",
        "bp machine showed 138 88 is that ok",
        "blood pressure keeps fluctuating through the day",
    ]),
    "cholesterol": (ROUTINE, [
        "what is a good cholesterol level",
        "how to reduce ldl",
        "is ghee bad for cholesterol",
        "what does triglycerides mean",
        "diet to lower cholesterol",
        "cholesterol kam kaise kare",
        "my total cholesterol is 240",
        "bad cholesterol came high in my report",
        "hdl is low what does that mean",
        "do i need a statin for this",
    ]),
    "thyroid": (ROUTINE, [
        "what is tsh",
        "my thyroid report is abnormal",
        "symptoms of hypothyroidism",
        "can thyroid cause weight gain",
        "thyroid ki dawai kab leni chahiye",
        "diet for thyroid patients",
        "my tsh value is 8",
        "thyroid report shows high tsh",
        "t3 and t4 are normal but tsh is not",
        "how often to repeat thyroid test",
    ]),
    "mental_health": (SEE_DOCTOR, [
        "i feel anxious all the time",
        "i have been feeling low for weeks",
        "how do i manage stress",
        "i cannot concentrate lately",
        "panic attacks at night",
        "tension bahut ho rahi hai",
        "is therapy worth it",
        "how to deal with burnout",
    ]),
    "pregnancy": (SEE_DOCTOR, [
        "what should i eat during pregnancy",
        "is it safe to exercise while pregnant",
        "which vitamins in pregnancy",
        "morning sickness remedies",
        "pregnancy me kya khana chahiye",
        "how often are check ups in pregnancy",
        "which foods are not allowed while pregnant",
        "things to avoid in the first three months",
        "is coffee ok during pregnancy",
        "can i take this tablet while pregnant",
    ]),
    "child_health": (SEE_DOCTOR, [
        "my child is not eating",
        "vaccination schedule for babies",
        "toddler has a rash",
        "how much sleep does a 5 year old need",
        "bacche ko bukhar hai",
        "when to start solid food for baby",
    ]),
    "lab_report": (ROUTINE, [
        "what does my report mean",
        "my haemoglobin is 10",
        "is fasting needed for a lipid profile",
        "how long do lab reports take",
        "what is a cbc test",
        "report kab tak aayega",
        "my vitamin d is low",
        "do i need to fast before the blood test",
    ]),
    "smoking_alcohol": (ROUTINE, [
        "how do i quit smoking",
        "how much alcohol is safe",
        "effects of smoking on lungs",
        "is one drink a day fine",
        "sigarette chodne ka tarika",
    ]),
    "vaccination": (ROUTINE, [
        "which vaccines do adults need",
        "should i get a flu shot",
        "is the tetanus shot needed",
        "vaccination ke baad bukhar aata hai kya",
        "is the flu shot worth taking every year",
        "which shots before travelling abroad",
        "am i due for any booster",
        "is the hpv vaccine recommended for adults",
    ]),
    "app_booking": (ROUTINE, [
        "how do i book an appointment",
        "can i book a lab test here",
        "how do i order my medicines",
        "how do i see my prescription",
        "where are my old reports",
        "how do i upload an old prescription",
        "how do i file an insurance claim",
        "how do i message my doctor",
        "what is included in premium",
        "how do i cancel my subscription",
    ]),
    "greeting": (ROUTINE, [
        "hi", "hello", "hey there", "good morning", "namaste",
        "are you there", "hi doc bot", "hello assistant",
    ]),
    "thanks": (ROUTINE, [
        "thanks", "thank you", "thanks a lot", "that helps", "got it thanks",
        "shukriya", "appreciate it", "perfect thanks",
    ]),
    "emergency": (EMERGENCY, [
        "i have chest pain",
        "crushing pain in my chest and left arm",
        "i cannot breathe properly",
        "severe breathlessness right now",
        "my father is unconscious",
        "she collapsed and is not responding",
        "bleeding heavily and it wont stop",
        "i think i am having a stroke",
        "face drooping and slurred speech",
        "having a seizure",
        "took too many tablets overdose",
        "i want to end my life",
        "i am thinking of harming myself",
        "coughing up blood",
        "severe stomach pain and vomiting blood",
        "sudden numbness on one side",
        "saans nahi aa rahi",
        "seene me dard ho raha hai",
        "baby is not breathing",
        "allergic reaction throat swelling",
        "very high fever with stiff neck and confusion",
        "accident head injury bleeding",
        "swallowed a whole strip of tablets",
        "he ate a bottle of pills",
        "she has taken all her medicines at once",
        "drank something poisonous",
        "chest feels tight and i am sweating",
        "crushing pressure in the chest",
        "sudden weakness on left side of body",
        "cannot speak properly all of a sudden",
        "heavy bleeding after a fall",
        "deep cut that will not stop bleeding",
    ]),
    "out_of_scope": (ROUTINE, [
        "what is the weather today",
        "tell me a joke",
        "who won the match",
        "what is your name",
        "can you write my essay",
        "book me a cab",
        "what is the stock price",
        "sing a song",
        "how are you",
        "translate this to french",
        "recommend a good film",
        "what should i watch this weekend",
        "suggest a series to binge",
        "who is the prime minister",
        "help me with my homework",
        "what time is the train",
        "order me a pizza",
    ]),
}

PREFIXES = ("", "", "", "hi ", "hey ", "can you tell me ", "please tell me ", "doctor ", "i wanted to ask ", "quick question ")
SUFFIXES = ("", "", "", "?", " ?", " pls", " please", " thanks", " tell me", "??")

# Surface-form swaps applied at random. Cheap paraphrasing that widens the
# vocabulary the classifier sees without hand-writing every variant.
SYNONYMS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("i am ", ("im ", "i'm ", "i m ")),
    ("i have ", ("i've got ", "im having ", "having ", "i got ")),
    ("should i ", ("do i need to ", "is it ok to ", "can i ", "must i ")),
    ("how much ", ("how many ", "what amount of ", "how much exactly ")),
    ("what is ", ("whats ", "what's ", "define ")),
    ("medicine", ("tablet", "meds", "dawai", "drug")),
    ("doctor", ("dr", "physician")),
    ("tablet", ("pill", "medicine", "tab")),
    ("exercise", ("workout", "physical activity")),
    ("water", ("fluids", "paani")),
    ("food", ("diet", "meals", "khana")),
    ("cannot", ("can't", "cant", "unable to")),
    ("stomach", ("tummy", "pet")),
    ("blood pressure", ("bp", "b.p.")),
    ("blood sugar", ("sugar level", "glucose")),
)


def _paraphrase(text: str, rng: np.random.Generator) -> str:
    for source, replacements in SYNONYMS:
        if source in text and rng.random() < 0.35:
            text = text.replace(source, str(rng.choice(replacements)), 1)
    return text


def _typo(text: str, rng: np.random.Generator) -> str:
    """Drop, double or swap one character — patients type on phones."""
    if len(text) < 6:
        return text
    index = int(rng.integers(1, len(text) - 1))
    roll = rng.random()
    if roll < 0.34:
        return text[:index] + text[index + 1:]
    if roll < 0.67:
        return text[:index] + text[index] + text[index:]
    return text[:index] + text[index + 1] + text[index] + text[index + 2:]


# Hand-written phrasings that appear nowhere in the seed templates. A random
# train/test split of generated variants mostly measures memorisation, so this
# is the split that actually says whether the classifier generalises.
HELD_OUT_CASES: tuple[tuple[str, str, str], ...] = (
    ("do i really need 8 glasses of water daily", "hydration", ROUTINE),
    ("i keep waking up at 3am every night", "sleep", ROUTINE),
    ("is brown rice better than white rice for me", "diet_general", ROUTINE),
    ("can i skip the gym and just do stairs", "exercise", ROUTINE),
    ("my weight has gone up 4 kg in two months", "weight_bmi", ROUTINE),
    ("forgot last nights tablet, take it in the morning?", "medication_missed_dose", ROUTINE),
    ("empty stomach or with breakfast for this tablet", "medication_timing", ROUTINE),
    ("since the new tablet i keep feeling sick", "medication_side_effect", SEE_DOCTOR),
    ("temperature 100.4 since yesterday evening", "fever", SEE_DOCTOR),
    ("throbbing pain in my head all afternoon", "headache", SEE_DOCTOR),
    ("throat is scratchy and i keep sneezing", "cold_cough", ROUTINE),
    ("loose motions three times today", "stomach", SEE_DOCTOR),
    ("fasting sugar came 142 is that bad", "diabetes", ROUTINE),
    ("bp reading was 148/92 this morning", "blood_pressure", ROUTINE),
    ("ldl is 165 what should i change", "cholesterol", ROUTINE),
    ("tsh came back at 8.2", "thyroid", ROUTINE),
    ("been feeling hopeless for a month now", "mental_health", SEE_DOCTOR),
    ("which foods to avoid in first trimester", "pregnancy", SEE_DOCTOR),
    ("my 3 year old wont eat anything", "child_health", SEE_DOCTOR),
    ("do i need to fast for the lipid test", "lab_report", ROUTINE),
    ("trying to stop smoking any tips", "smoking_alcohol", ROUTINE),
    ("do i need the flu vaccine this year", "vaccination", ROUTINE),
    ("where do i upload my old x ray", "app_booking", ROUTINE),
    ("hey good evening", "greeting", ROUTINE),
    ("thanks that was useful", "thanks", ROUTINE),
    ("tightness in my chest radiating to the arm", "emergency", EMERGENCY),
    ("my mother has collapsed and wont wake up", "emergency", EMERGENCY),
    ("struggling to breathe since an hour", "emergency", EMERGENCY),
    ("i dont want to be alive anymore", "emergency", EMERGENCY),
    ("swallowed a whole strip of pills", "emergency", EMERGENCY),
    ("what movie should i watch tonight", "out_of_scope", ROUTINE),
)


def build_corpus(seed: int = 7, variants_per_phrase: int = 12) -> tuple[list[str], list[str], list[str]]:
    """Return (texts, intents, urgency labels), de-duplicated."""
    rng = np.random.default_rng(seed)
    texts, intents, urgencies = [], [], []
    seen: set[tuple[str, str]] = set()

    for intent, (urgency, phrases) in INTENTS.items():
        for phrase in phrases:
            for variant in range(variants_per_phrase):
                text = phrase
                if variant > 0:
                    text = _paraphrase(text, rng)
                    text = str(rng.choice(PREFIXES)) + text + str(rng.choice(SUFFIXES))
                    if rng.random() < 0.22:
                        text = _typo(text, rng)
                    if rng.random() < 0.12:
                        text = text.upper() if rng.random() < 0.4 else text.capitalize()
                text = text.strip()
                key = (text.lower(), intent)
                if key in seen:
                    continue
                seen.add(key)
                texts.append(text)
                intents.append(intent)
                urgencies.append(urgency)

    return texts, intents, urgencies
