"""English curriculum skills, seeded to app.models.language.Skill. Keeping this
as a per-language module under learning/languages/<code>/ (section 84) is the
extension point for adding another target language without touching the engine:
add learning/languages/es/grammar_topics.py with the same shape and register it
in curriculum.CURRICULUM_BY_LANGUAGE.
"""

EN_SKILLS = [
    # A1
    {"code": "basic_nouns", "name": "Basic Nouns", "category": "grammar", "cefr_level": "A1", "description": "Common nouns and pluralization."},
    {"code": "pronouns", "name": "Pronouns", "category": "grammar", "cefr_level": "A1", "description": "Subject and object pronouns."},
    {"code": "present_simple", "name": "Present Simple", "category": "grammar", "cefr_level": "A1", "description": "Present simple tense for habits and facts."},
    {"code": "basic_questions", "name": "Basic Questions", "category": "grammar", "cefr_level": "A1", "description": "Forming yes/no and wh- questions."},
    {"code": "articles", "name": "Articles", "category": "grammar", "cefr_level": "A1", "description": "a/an/the usage."},
    # A2
    {"code": "past_tense", "name": "Past Tense", "category": "grammar", "cefr_level": "A2", "description": "Simple past for completed actions, including irregular verbs."},
    {"code": "future_tense", "name": "Future Tense", "category": "grammar", "cefr_level": "A2", "description": "will / going to for future plans."},
    {"code": "comparatives", "name": "Comparatives & Superlatives", "category": "grammar", "cefr_level": "A2", "description": "Comparing nouns."},
    {"code": "prepositions", "name": "Prepositions", "category": "grammar", "cefr_level": "A2", "description": "Common prepositions of time and place."},
    # B1
    {"code": "conditionals", "name": "Conditionals", "category": "grammar", "cefr_level": "B1", "description": "Zero, first, and second conditional."},
    {"code": "complex_sentences", "name": "Complex Sentences", "category": "grammar", "cefr_level": "B1", "description": "Joining clauses with conjunctions."},
    {"code": "phrasal_verbs", "name": "Phrasal Verbs", "category": "vocabulary", "cefr_level": "B1", "description": "Common phrasal verbs."},
    {"code": "present_perfect", "name": "Present Perfect", "category": "grammar", "cefr_level": "B1", "description": "Present perfect vs. simple past."},
    # B2
    {"code": "advanced_grammar", "name": "Advanced Grammar", "category": "grammar", "cefr_level": "B2", "description": "Passive voice, reported speech."},
    {"code": "idioms", "name": "Idioms", "category": "vocabulary", "cefr_level": "B2", "description": "Common idiomatic expressions."},
    {"code": "register", "name": "Formal/Informal Register", "category": "vocabulary", "cefr_level": "B2", "description": "Choosing appropriate register."},
    # C1
    {"code": "nuanced_expression", "name": "Nuanced Expression", "category": "vocabulary", "cefr_level": "C1", "description": "Precise, nuanced word choice."},
    {"code": "academic_vocabulary", "name": "Academic Vocabulary", "category": "vocabulary", "cefr_level": "C1", "description": "Formal/academic register vocabulary."},
    {"code": "advanced_syntax", "name": "Advanced Syntax", "category": "grammar", "cefr_level": "C1", "description": "Complex clause structures."},
    # C2
    {"code": "native_nuance", "name": "Native-like Nuance", "category": "vocabulary", "cefr_level": "C2", "description": "Subtle connotation and idiom mastery."},
    {"code": "stylistic_control", "name": "Stylistic Control", "category": "writing", "cefr_level": "C2", "description": "Controlling tone and style deliberately."},
    # Cross-level skill-area anchors (used for skill_mastery rollups on non-grammar dimensions)
    {"code": "vocabulary_range", "name": "Vocabulary Range", "category": "vocabulary", "cefr_level": "A2", "description": "Breadth of active vocabulary."},
    {"code": "pronunciation_general", "name": "Pronunciation", "category": "pronunciation", "cefr_level": "A2", "description": "General pronunciation accuracy."},
    {"code": "fluency_general", "name": "Fluency", "category": "fluency", "cefr_level": "A2", "description": "Speaking fluency and flow."},
]
