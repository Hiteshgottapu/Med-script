"""
MedScript AI Consultant & Disease Prediction Service
"""

import os
import ast
import pickle
import logging
from collections import defaultdict
import numpy as np
import pandas as pd
from textblob import TextBlob

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATASET_DIR = os.path.join(BASE_DIR, "dataset")
MODEL_DIR = os.path.join(BASE_DIR, "model")

symptoms_dict = {
    'itching': 0, 'skin_rash': 1, 'nodal_skin_eruptions': 2, 'continuous_sneezing': 3,
    'shivering': 4, 'chills': 5, 'joint_pain': 6, 'stomach_pain': 7, 'acidity': 8,
    'ulcers_on_tongue': 9, 'muscle_wasting': 10, 'vomiting': 11, 'burning_micturition': 12,
    'spotting_urination': 13, 'fatigue': 14, 'weight_gain': 15, 'anxiety': 16,
    'cold_hands_and_feets': 17, 'mood_swings': 18, 'weight_loss': 19, 'restlessness': 20,
    'lethargy': 21, 'patches_in_throat': 22, 'irregular_sugar_level': 23, 'cough': 24,
    'high_fever': 25, 'sunken_eyes': 26, 'breathlessness': 27, 'sweating': 28,
    'dehydration': 29, 'indigestion': 30, 'headache': 31, 'yellowish_skin': 32,
    'dark_urine': 33, 'nausea': 34, 'loss_of_appetite': 35, 'pain_behind_the_eyes': 36,
    'back_pain': 37, 'constipation': 38, 'abdominal_pain': 39, 'diarrhoea': 40,
    'mild_fever': 41, 'yellow_urine': 42, 'yellowing_of_eyes': 43, 'acute_liver_failure': 44,
    'fluid_overload': 45, 'swelling_of_stomach': 46, 'swelled_lymph_nodes': 47, 'malaise': 48,
    'blurred_and_distorted_vision': 49, 'phlegm': 50, 'throat_irritation': 51, 'redness_of_eyes': 52,
    'sinus_pressure': 53, 'runny_nose': 54, 'congestion': 55, 'chest_pain': 56,
    'weakness_in_limbs': 57, 'fast_heart_rate': 58, 'pain_during_bowel_movements': 59,
    'pain_in_anal_region': 60, 'bloody_stool': 61, 'irritation_in_anus': 62, 'neck_pain': 63,
    'dizziness': 64, 'cramps': 65, 'bruising': 66, 'obesity': 67, 'swollen_legs': 68,
    'swollen_blood_vessels': 69, 'puffy_face_and_eyes': 70, 'enlarged_thyroid': 71,
    'brittle_nails': 72, 'swollen_extremeties': 73, 'excessive_hunger': 74, 'extra_marital_contacts': 75,
    'drying_and_tingling_lips': 76, 'slurred_speech': 77, 'knee_pain': 78, 'hip_joint_pain': 79,
    'muscle_weakness': 80, 'stiff_neck': 81, 'swelling_joints': 82, 'movement_stiffness': 83,
    'spinning_movements': 84, 'loss_of_balance': 85, 'unsteadiness': 86, 'weakness_of_one_body_side': 87,
    'loss_of_smell': 88, 'bladder_discomfort': 89, 'foul_smell_of urine': 90, 'continuous_feel_of_urine': 91,
    'passage_of_gases': 92, 'internal_itching': 93, 'toxic_look_(typhos)': 94, 'depression': 95,
    'irritability': 96, 'muscle_pain': 97, 'altered_sensorium': 98, 'red_spots_over_body': 99,
    'belly_pain': 100, 'abnormal_menstruation': 101, 'dischromic _patches': 102, 'watering_from_eyes': 103,
    'increased_appetite': 104, 'polyuria': 105, 'family_history': 106, 'mucoid_sputum': 107,
    'rusty_sputum': 108, 'lack_of_concentration': 109, 'visual_disturbances': 110,
    'receiving_blood_transfusion': 111, 'receiving_unsterile_injections': 112, 'coma': 113,
    'stomach_bleeding': 114, 'distention_of_abdomen': 115, 'history_of_alcohol_consumption': 116,
    'fluid_overload.1': 117, 'blood_in_sputum': 118, 'prominent_veins_on_calf': 119,
    'palpitations': 120, 'painful_walking': 121, 'pus_filled_pimples': 122, 'blackheads': 123,
    'scurring': 124, 'skin_peeling': 125, 'silver_like_dusting': 126, 'small_dents_in_nails': 127,
    'inflammatory_nails': 128, 'blister': 129, 'red_sore_around_nose': 130, 'yellow_crust_ooze': 131
}

diseases_list = {
    15: 'Fungal infection', 4: 'Allergy', 16: 'GERD', 9: 'Chronic cholestasis',
    14: 'Drug Reaction', 33: 'Peptic ulcer diseae', 1: 'AIDS', 12: 'Diabetes',
    17: 'Gastroenteritis', 6: 'Bronchial Asthma', 23: 'Hypertension', 30: 'Migraine',
    7: 'Cervical spondylosis', 32: 'Paralysis (brain hemorrhage)', 28: 'Jaundice',
    29: 'Malaria', 8: 'Chicken pox', 11: 'Dengue', 37: 'Typhoid', 40: 'hepatitis A',
    19: 'Hepatitis B', 20: 'Hepatitis C', 21: 'Hepatitis D', 22: 'Hepatitis E',
    3: 'Alcoholic hepatitis', 36: 'Tuberculosis', 10: 'Common Cold', 34: 'Pneumonia',
    13: 'Dimorphic hemmorhoids(piles)', 18: 'Heart attack', 39: 'Varicose veins',
    26: 'Hypothyroidism', 24: 'Hyperthyroidism', 25: 'Hypoglycemia', 31: 'Osteoarthristis',
    5: 'Arthritis', 0: '(vertigo) Paroymsal Positional Vertigo', 2: 'Acne',
    38: 'Urinary tract infection', 35: 'Psoriasis', 27: 'Impetigo'
}

symptom_mapping = defaultdict(lambda: "unknown", {
    "itching": ["itching"],
    "skin_rash": ["skin rash", "rash", "dermatitis", "rashes"],
    "nodal_skin_eruptions": ["nodal skin eruptions", "skin eruptions", "bumps"],
    "continuous_sneezing": ["continuous sneezing", "sneezing"],
    "shivering": ["shivering", "trembling"],
    "chills": ["chills", "cold sensation", "cold"],
    "joint_pain": ["joint pain", "arthralgia", "aching joints"],
    "stomach_pain": ["stomach pain", "abdominal pain", "belly ache"],
    "acidity": ["acidity", "heartburn", "acid reflux"],
    "ulcers_on_tongue": ["ulcers on tongue", "tongue ulcers", "mouth sores"],
    "muscle_wasting": ["muscle wasting", "muscle loss"],
    "vomiting": ["vomiting", "emesis", "throwing up"],
    "burning_micturition": ["burning micturition", "burning urination", "painful urination"],
    "spotting_urination": ["spotting urination", "blood in urine", "hematuria"],
    "fatigue": ["fatigue", "tiredness", "exhaustion"],
    "weight_gain": ["weight gain", "increased weight"],
    "anxiety": ["anxiety", "nervousness", "worry", "sleeping"],
    "cold_hands_and_feets": ["cold hands and feet", "cold extremities"],
    "mood_swings": ["mood swings", "emotional changes"],
    "weight_loss": ["weight loss", "decreased weight"],
    "restlessness": ["restlessness", "agitation"],
    "lethargy": ["lethargy", "sluggishness"],
    "patches_in_throat": ["patches in throat", "throat patches", "throat lesions"],
    "irregular_sugar_level": ["irregular sugar level", "unstable glucose", "blood sugar fluctuations"],
    "cough": ["cough", "coughing"],
    "high_fever": ["high fever", "elevated temperature"],
    "sunken_eyes": ["sunken eyes", "hollow eyes"],
    "breathlessness": ["breathlessness", "shortness of breath", "dyspnea"],
    "sweating": ["sweating", "perspiration"],
    "dehydration": ["dehydration", "fluid loss"],
    "indigestion": ["indigestion", "upset stomach"],
    "headache": ["headache", "head pain", "migraine"],
    "yellowish_skin": ["yellowish skin", "jaundice"],
    "dark_urine": ["dark urine"],
    "swelled_lymph_nodes": ["swelled lymph nodes", "enlarged lymph nodes"],
    "malaise": ["malaise", "general discomfort"],
    "blurred_and_distorted_vision": ["blurred and distorted vision", "blurry vision"],
    "phlegm": ["phlegm", "mucus"],
    "throat_irritation": ["throat irritation", "sore throat"],
    "redness_of_eyes": ["redness of eyes", "bloodshot eyes"],
    "sinus_pressure": ["sinus pressure", "sinus congestion"],
    "runny_nose": ["runny nose", "rhinorrhea"],
    "congestion": ["congestion", "nasal blockage"],
    "chest_pain": ["chest pain", "angina"],
    "weakness_in_limbs": ["weakness in limbs", "limb weakness"],
    "fast_heart_rate": ["fast heart rate", "tachycardia"],
    "pain_during_bowel_movements": ["pain during bowel movements", "painful defecation"],
    "pain_in_anal_region": ["pain in anal region", "anal pain"],
    "bloody_stool": ["bloody stool", "rectal bleeding"],
    "irritation_in_anus": ["irritation in anus", "anal itching"],
    "neck_pain": ["neck pain", "cervical pain"],
    "dizziness": ["dizziness", "lightheadedness"],
    "cramps": ["cramps", "muscle cramps", "spasms"],
    "bruising": ["bruising", "hematoma"],
    "obesity": ["obesity", "overweight"],
    "swollen_legs": ["swollen legs", "leg edema"],
    "swollen_blood_vessels": ["swollen blood vessels", "varicose veins"],
    "puffy_face_and_eyes": ["puffy face and eyes", "facial swelling"],
    "enlarged_thyroid": ["enlarged thyroid", "goiter"],
    "brittle_nails": ["brittle nails", "weak nails"],
    "swollen_extremeties": ["swollen extremities", "swollen arms and legs"],
    "excessive_hunger": ["excessive hunger", "polyphagia"],
    "extra_marital_contacts": ["extra marital contacts", "multiple sexual partners"],
    "drying_and_tingling_lips": ["drying and tingling lips", "lip dryness"],
    "slurred_speech": ["slurred speech", "dysarthria"],
    "knee_pain": ["knee pain", "pain in the knees"],
    "hip_joint_pain": ["hip joint pain", "hip pain"],
    "muscle_weakness": ["muscle weakness", "muscle fatigue"],
    "stiff_neck": ["stiff neck", "neck stiffness"],
    "swelling_joints": ["swelling joints", "joint swelling"],
    "movement_stiffness": ["movement stiffness", "rigidity"],
    "spinning_movements": ["spinning movements", "vertigo"],
    "loss_of_balance": ["loss of balance", "balance problems"],
    "unsteadiness": ["unsteadiness", "lack of balance"],
    "weakness_of_one_body_side": ["weakness of one body side", "hemiparesis"],
    "loss_of_smell": ["loss of smell", "anosmia"],
    "bladder_discomfort": ["bladder discomfort", "bladder pain"],
    "foul_smell_of urine": ["foul smell of urine", "smelly urine"],
    "continuous_feel_of_urine": ["continuous feel of urine", "urgency to urinate"],
    "passage_of_gases": ["passage of gases", "flatulence"],
    "internal_itching": ["internal itching"],
    "toxic_look_(typhos)": ["toxic look (typhos)", "septic appearance"],
    "depression": ["depression", "low mood"],
    "irritability": ["irritability", "easily annoyed"],
    "muscle_pain": ["muscle pain", "myalgia"],
    "altered_sensorium": ["altered sensorium", "confusion"],
    "red_spots_over_body": ["red spots over body", "rash with red spots"],
    "belly_pain": ["belly pain", "abdominal pain"],
    "abnormal_menstruation": ["abnormal menstruation", "irregular periods"],
    "dischromic_patches": ["dischromic patches", "skin discoloration"],
    "watering_from_eyes": ["watering from eyes", "teary eyes"],
    "increased_appetite": ["increased appetite", "hyperphagia"],
    "polyuria": ["polyuria", "excessive urination"],
    "family_history": ["family history", "genetic predisposition"],
    "mucoid_sputum": ["mucoid sputum", "mucus in sputum"],
    "rusty_sputum": ["rusty sputum", "blood-tinged sputum"],
    "lack_of_concentration": ["lack of concentration", "difficulty focusing"],
    "visual_disturbances": ["visual disturbances", "vision problems"],
    "receiving_blood_transfusion": ["receiving blood transfusion"],
    "receiving_unsterile_injections": ["receiving unsterile injections"]
})


class DiseasePredictorService:
    def __init__(self):
        self._model = None
        self._datasets_loaded = False
        self.description = None
        self.precautions = None
        self.medications = None
        self.diets = None
        self.workout = None

    def _load_resources(self):
        if self._datasets_loaded:
            return
        try:
            model_path = os.path.join(MODEL_DIR, "svc.pkl")
            if os.path.exists(model_path):
                with open(model_path, "rb") as f:
                    self._model = pickle.load(f)

            desc_path = os.path.join(DATASET_DIR, "description.csv")
            prec_path = os.path.join(DATASET_DIR, "precautions_df.csv")
            med_path = os.path.join(DATASET_DIR, "medications.csv")
            diet_path = os.path.join(DATASET_DIR, "diets.csv")
            work_path = os.path.join(DATASET_DIR, "workout_df.csv")

            if os.path.exists(desc_path): self.description = pd.read_csv(desc_path)
            if os.path.exists(prec_path): self.precautions = pd.read_csv(prec_path)
            if os.path.exists(med_path): self.medications = pd.read_csv(med_path)
            if os.path.exists(diet_path): self.diets = pd.read_csv(diet_path)
            if os.path.exists(work_path): self.workout = pd.read_csv(work_path)

            self._datasets_loaded = True
        except Exception as e:
            logging.error(f"Error loading disease datasets/model: {e}")

    def correct_spelling(self, symptom):
        try:
            blob = TextBlob(symptom)
            return str(blob.correct())
        except Exception:
            return symptom

    def get_top_predicted_values(self, patient_symptoms, top_n=3):
        self._load_resources()
        input_vector = np.zeros(len(symptoms_dict))
        for item in patient_symptoms:
            index = symptoms_dict.get(item, -1)
            if index != -1:
                input_vector[index] = 1
            else:
                found = False
                for key, synonyms in symptom_mapping.items():
                    if item in synonyms:
                        index = symptoms_dict.get(key, -1)
                        if index != -1:
                            input_vector[index] = 1
                            found = True
                            break
                if not found:
                    corrected = self.correct_spelling(item)
                    index = symptoms_dict.get(corrected, -1)
                    if index != -1:
                        input_vector[index] = 1
                    else:
                        for key, synonyms in symptom_mapping.items():
                            if corrected in synonyms:
                                index = symptoms_dict.get(key, -1)
                                if index != -1:
                                    input_vector[index] = 1
                                    break

        if not self._model:
            return [(15, 'Fungal infection')]

        if hasattr(self._model, "predict_proba"):
            probs = self._model.predict_proba([input_vector])[0]
            top_indices = np.argsort(probs)[::-1][:top_n]
        else:
            pred = self._model.predict([input_vector])[0]
            top_indices = [pred]

        top_diseases = []
        for idx in top_indices:
            disease = diseases_list.get(idx, "Unknown Condition")
            top_diseases.append((idx, disease))
        return top_diseases

    def _parse_csv_list_values(self, series_val):
        if series_val is None:
            return []
        items = []
        for val in series_val:
            if isinstance(val, (list, tuple)):
                for v in val:
                    if v is not None and pd.notna(v) and str(v).strip():
                        items.append(str(v).strip())
            elif isinstance(val, str):
                val_str = val.strip()
                if val_str.startswith('[') and val_str.endswith(']'):
                    try:
                        parsed = ast.literal_eval(val_str)
                        if isinstance(parsed, (list, tuple)):
                            for p in parsed:
                                if p is not None and pd.notna(p) and str(p).strip():
                                    items.append(str(p).strip())
                            continue
                    except Exception:
                        pass
                val_cleaned = val_str.strip("'\"")
                if val_cleaned and pd.notna(val_cleaned):
                    items.append(val_cleaned)
        return items

    def get_disease_details(self, dis):
        self._load_resources()
        desc_str = ""
        pre_list = []
        med_list = []
        diet_list = []
        work_list = []

        if self.description is not None:
            desc_val = self.description[self.description['Disease'] == dis]['Description']
            desc_str = " ".join([str(w) for w in desc_val if pd.notna(w)])

        if self.precautions is not None:
            pre_df = self.precautions[self.precautions['Disease'] == dis]
            cols = [c for c in ['Precaution_1', 'Precaution_2', 'Precaution_3', 'Precaution_4'] if c in pre_df.columns]
            if cols:
                raw_prec = pre_df[cols].values.flatten()
                pre_list = [str(p).strip().capitalize() for p in raw_prec if pd.notna(p) and str(p).strip()]

        if self.medications is not None:
            med_val = self.medications[self.medications['Disease'] == dis]['Medication']
            med_list = self._parse_csv_list_values(med_val.values)

        if self.diets is not None:
            diet_val = self.diets[self.diets['Disease'] == dis]['Diet']
            diet_list = self._parse_csv_list_values(diet_val.values)

        if self.workout is not None:
            work_val = self.workout[self.workout['disease'] == dis]['workout']
            work_list = self._parse_csv_list_values(work_val.values)

        return desc_str, pre_list, med_list, diet_list, work_list


consultant_service = DiseasePredictorService()
