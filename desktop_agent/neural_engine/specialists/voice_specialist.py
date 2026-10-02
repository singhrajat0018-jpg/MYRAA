"""Voice Neural Specialist — enhances existing ContinuousVoiceLoop.

Flow:
ContinuousVoiceLoop → transcript + audio features → Voice Neural Model
→ enhanced voice intelligence → result → ContextFusion → Super-Brain

DO NOT replace the STT/TTS pipeline. This specialist analyzes transcripts
and provides intent cues, emotion detection, turn-taking signals, and
prosody features that the voice loop consumes.
"""

from __future__ import annotations

import re
import time
import threading
from typing import Any, Optional
from dataclasses import dataclass, field

from ..model_contract import (
    ModelSpec, ModelResult, InferenceRequest, ModelDomain, ModelModality,
    LatencyClass, ModelDeployment, ModelStatus,
)


@dataclass
class IntentCue:
    """Detected intent signal from transcript text."""
    intent: str
    confidence: float
    keywords: list[str] = field(default_factory=list)
    is_question: bool = False
    is_command: bool = False
    is_statement: bool = False


@dataclass
class EmotionSignal:
    """Basic emotion/tonality signal from transcript."""
    primary: str
    confidence: float
    valence: float = 0.0
    arousal: float = 0.0
    secondary: Optional[str] = None


@dataclass
class TurnSignal:
    """Speaker turn-taking information."""
    turn_number: int
    speaker: str
    is_complete: bool = True
    pause_before_ms: float = 0.0
    interruption_detected: bool = False
    topic_shift: bool = False


@dataclass
class ProsodyFeatures:
    """Extracted prosody features from transcript/context."""
    emphasis_words: list[str] = field(default_factory=list)
    repetition_detected: bool = False
    hesitation_markers: list[str] = field(default_factory=list)
    speech_rate_estimate: Optional[str] = None
    question_markers: list[str] = field(default_factory=list)


@dataclass
class VoiceAnalysis:
    """Structured voice neural output."""
    intent_cues: list[IntentCue] = field(default_factory=list)
    emotion: Optional[EmotionSignal] = None
    turn_signals: list[TurnSignal] = field(default_factory=list)
    prosody_features: Optional[ProsodyFeatures] = None
    speech_quality: float = 0.0
    has_question: bool = False
    has_command: bool = False
    turn_count: int = 0
    confidence: float = 0.5


class VoiceSpecialist:
    """Voice specialist model — transcript intelligence only.

    Does NOT perform STT or TTS. Analyzes transcripts from the existing
    ContinuousVoiceLoop and provides enriched signals for the brain pipeline.
    """

    SPEC = ModelSpec(
        model_id="voice_specialist_v1",
        domain=ModelDomain.VOICE,
        version="1.0.0",
        modality=ModelModality.AUDIO,
        capabilities=[
            "speech_enhancement",
            "intent_cues",
            "emotion_detection",
            "speaker_turn_detection",
            "prosody_analysis",
        ],
        input_schema={
            "transcript": "str",
            "audio_features": "dict",
            "context": "dict",
        },
        output_schema={
            "analysis": "VoiceAnalysis",
            "confidence": "float",
        },
        latency_class=LatencyClass.FAST,
        deployment=ModelDeployment.LOCAL,
        resource_requirements={"min_memory_mb": 64},
        provider="local",
    )

    _QUESTION_PATTERN = re.compile(
        r"\b(what|how|why|when|where|who|which|can|could|would|should|do|does|did|is|are|was|were|have|has|had|will|shall|may|might)\b",
        re.IGNORECASE,
    )
    _COMMAND_PATTERNS = (
        re.compile(r"\b(open|close|run|stop|start|search|find|show|hide|create|delete|move|copy|send|play|pause|volume|brightness)\b", re.IGNORECASE),
        re.compile(r"^\s*(please|hey|can you|could you|would you|do)\b", re.IGNORECASE),
    )
    _EMOTION_KEYWORDS: dict[str, list[str]] = {
        "frustrated": ["annoying", "stupid", "hate", "ugh", "frustrating", "broken", "useless", "terrible", "awful"],
        "excited": ["awesome", "amazing", "great", "love", "excellent", "fantastic", "incredible", "perfect", "wow"],
        "confused": ["confused", "unclear", "don't understand", "what do you mean", "huh", "wait", "lost"],
        "satisfied": ["thanks", "thank you", "good", "nice", "helpful", "appreciate", "perfect", "got it"],
        "neutral": [],
    }
    _HESITATION_MARKERS = ("um", "uh", "er", "ah", "hmm", "mm", "let me see", "well", "so")
    _EMPHASIS_MARKERS = ("really", "very", "absolutely", "definitely", "never", "always", "must", "critical", "important")

    def __init__(self):
        self._status = ModelStatus.ACTIVE
        self._health_score: float = 1.0
        self._total_calls: int = 0
        self._failures: int = 0
        self._lock = threading.Lock()

    @property
    def model_id(self) -> str:
        return self.SPEC.model_id

    @property
    def status(self) -> ModelStatus:
        return self._status

    def inference(self, request: InferenceRequest) -> ModelResult:
        start = time.perf_counter()
        with self._lock:
            self._total_calls += 1

        try:
            transcript = request.context.get("transcript", "")
            audio_features = request.context.get("audio_features", {})
            context = request.context.get("context", {})

            analysis = self._analyze(transcript, audio_features, context)

            elapsed = (time.perf_counter() - start) * 1000
            self._update_health(True)

            return ModelResult(
                model_id=self.model_id,
                output=analysis,
                confidence=analysis.confidence,
                uncertainty=1.0 - analysis.confidence,
                latency_ms=elapsed,
                timestamp=time.time(),
                source="voice_specialist",
                version=self.SPEC.version,
            )
        except Exception as e:
            elapsed = (time.perf_counter() - start) * 1000
            with self._lock:
                self._failures += 1
            self._update_health(False)
            return ModelResult(
                model_id=self.model_id,
                output=VoiceAnalysis(confidence=0.0),
                confidence=0.0,
                uncertainty=1.0,
                latency_ms=elapsed,
                timestamp=time.time(),
                source="voice_specialist_error",
                warnings=[str(e)],
                version=self.SPEC.version,
            )

    def _analyze(
        self, transcript: str, audio_features: dict, context: dict
    ) -> VoiceAnalysis:
        intent_cues = self._analyze_intent_cues(transcript)
        emotion = self._detect_emotion(transcript, audio_features)
        turn_signals = self._analyze_turn_taking(transcript, context)
        prosody_features = self._extract_prosody(transcript)
        speech_quality = self._assess_speech_quality(transcript, audio_features)

        has_question = any(ic.is_question for ic in intent_cues)
        has_command = any(ic.is_command for ic in intent_cues)

        confidences = [ic.confidence for ic in intent_cues]
        if emotion:
            confidences.append(emotion.confidence)
        overall = sum(confidences) / len(confidences) if confidences else 0.5

        return VoiceAnalysis(
            intent_cues=intent_cues,
            emotion=emotion,
            turn_signals=turn_signals,
            prosody_features=prosody_features,
            speech_quality=speech_quality,
            has_question=has_question,
            has_command=has_command,
            turn_count=len(turn_signals),
            confidence=min(1.0, overall),
        )

    def _analyze_intent_cues(self, transcript: str) -> list[IntentCue]:
        if not transcript or not transcript.strip():
            return []

        cues: list[IntentCue] = []
        words = transcript.strip().split()
        text_lower = transcript.lower().strip()

        is_question = text_lower.endswith("?") or bool(self._QUESTION_PATTERN.search(transcript))

        is_command = False
        matched_command_kw: list[str] = []
        for pattern in self._COMMAND_PATTERNS:
            match = pattern.search(transcript)
            if match:
                is_command = True
                matched_command_kw.append(match.group(0))

        if is_question:
            keywords = self._extract_keywords(transcript)
            cues.append(IntentCue(
                intent="question",
                confidence=0.85,
                keywords=keywords,
                is_question=True,
                is_command=False,
                is_statement=False,
            ))

        if is_command:
            keywords = matched_command_kw + self._extract_keywords(transcript)
            cues.append(IntentCue(
                intent="command",
                confidence=0.8,
                keywords=keywords,
                is_question=False,
                is_command=True,
                is_statement=False,
            ))

        if not is_question and not is_command:
            keywords = self._extract_keywords(transcript)
            cues.append(IntentCue(
                intent="statement",
                confidence=0.6,
                keywords=keywords,
                is_question=False,
                is_command=False,
                is_statement=True,
            ))

        greeting = re.match(r"\b(hi|hello|hey|yo|namaste|good\s+(morning|afternoon|evening))\b", text_lower)
        if greeting:
            cues.append(IntentCue(
                intent="greeting",
                confidence=0.9,
                keywords=[greeting.group(0)],
            ))

        farewell = re.search(r"\b(bye|goodbye|see you|talk later|good night)\b", text_lower)
        if farewell:
            cues.append(IntentCue(
                intent="farewell",
                confidence=0.85,
                keywords=[farewell.group(0)],
            ))

        return cues

    def _detect_emotion(
        self, transcript: str, audio_features: dict
    ) -> Optional[EmotionSignal]:
        if not transcript and not audio_features:
            return None

        text_lower = transcript.lower() if transcript else ""
        best_emotion = "neutral"
        best_score = 0.0

        for emotion, keywords in self._EMOTION_KEYWORDS.items():
            if not keywords:
                continue
            matches = sum(1 for kw in keywords if kw in text_lower)
            score = matches / len(keywords)
            if score > best_score:
                best_score = score
                best_emotion = emotion

        if best_emotion == "neutral" or best_score == 0.0:
            exclamation_count = transcript.count("!") if transcript else 0
            if exclamation_count >= 2:
                best_emotion = "excited"
                best_score = 0.6
            elif exclamation_count == 1 and len(transcript.split()) < 6:
                best_emotion = "excited"
                best_score = 0.4

        confidence = min(0.9, 0.4 + best_score * 0.5)
        valence = {"frustrated": -0.6, "confused": -0.2, "neutral": 0.0, "satisfied": 0.5, "excited": 0.8}.get(best_emotion, 0.0)
        arousal = {"frustrated": 0.6, "excited": 0.7, "confused": 0.3, "neutral": 0.2, "satisfied": 0.3}.get(best_emotion, 0.2)

        secondary = None
        if best_emotion != "neutral":
            scores = {}
            for emo, kws in self._EMOTION_KEYWORDS.items():
                if emo == best_emotion or not kws:
                    continue
                s = sum(1 for kw in kws if kw in text_lower) / len(kws)
                if s > 0.1:
                    scores[emo] = s
            if scores:
                secondary = max(scores, key=scores.get)

        return EmotionSignal(
            primary=best_emotion,
            confidence=confidence,
            valence=valence,
            arousal=arousal,
            secondary=secondary,
        )

    def _analyze_turn_taking(
        self, transcript: str, context: dict
    ) -> list[TurnSignal]:
        if not transcript:
            return []

        history = context.get("transcript_history", [])
        turn_number = context.get("turn_number", 0)
        last_speaker = context.get("last_speaker", "unknown")
        pause_ms = context.get("pause_before_ms", 0.0)
        interruption = context.get("interruption_detected", False)

        if turn_number == 0 and not history:
            turn_number = 1

        topic_shift = False
        if history and len(history) > 0:
            last_text = history[-1] if isinstance(history[-1], str) else str(history[-1])
            topic_shift = self._detect_topic_shift(last_text, transcript)

        current_speaker = "user"
        if last_speaker == "user":
            current_speaker = "assistant"

        return [TurnSignal(
            turn_number=turn_number,
            speaker=current_speaker,
            is_complete=True,
            pause_before_ms=pause_ms,
            interruption_detected=interruption,
            topic_shift=topic_shift,
        )]

    def _extract_prosody(self, transcript: str) -> ProsodyFeatures:
        if not transcript:
            return ProsodyFeatures()

        words = transcript.split()
        text_lower = transcript.lower()

        emphasis_words = [w for w in words if w.lower() in self._EMPHASIS_MARKERS]

        repetition_detected = False
        for i in range(len(words) - 1):
            if words[i].lower() == words[i + 1].lower():
                repetition_detected = True
                break

        hesitations = [m for m in self._HESITATION_MARKERS if m in text_lower]

        word_count = len(words)
        if word_count < 3:
            rate = "slow"
        elif word_count < 10:
            rate = "normal"
        else:
            rate = "fast"

        question_marks = []
        for i, sent in enumerate(re.split(r"[.!?]+", transcript)):
            if sent.strip().endswith("?"):
                question_marks.append(sent.strip()[:40])

        return ProsodyFeatures(
            emphasis_words=emphasis_words,
            repetition_detected=repetition_detected,
            hesitation_markers=hesitations,
            speech_rate_estimate=rate,
            question_markers=question_marks,
        )

    def _assess_speech_quality(
        self, transcript: str, audio_features: dict
    ) -> float:
        if not transcript:
            return 0.0

        score = 0.5
        words = transcript.split()
        word_count = len(words)

        if word_count == 0:
            return 0.0

        if word_count >= 3:
            score += 0.1
        if word_count >= 8:
            score += 0.1

        hesitation_count = sum(1 for m in self._HESITATION_MARKERS if m in transcript.lower())
        score -= hesitation_count * 0.03

        if transcript.strip().endswith((".", "!", "?")):
            score += 0.05

        unique_ratio = len(set(w.lower() for w in words)) / word_count
        score += unique_ratio * 0.1

        snr = audio_features.get("signal_to_noise_db")
        if snr is not None:
            if snr > 20:
                score += 0.1
            elif snr < 5:
                score -= 0.1

        confidence = audio_features.get("stt_confidence")
        if confidence is not None:
            score = score * 0.7 + confidence * 0.3

        return max(0.0, min(1.0, score))

    def _extract_keywords(self, transcript: str) -> list[str]:
        stopwords = {
            "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
            "have", "has", "had", "do", "does", "did", "will", "would", "could",
            "should", "may", "might", "can", "shall", "to", "of", "in", "for",
            "on", "with", "at", "by", "from", "it", "this", "that", "i", "you",
            "he", "she", "we", "they", "me", "him", "her", "us", "them", "my",
            "your", "his", "its", "our", "their", "and", "or", "but", "if", "so",
            "not", "no", "yes", "just", "also", "very", "too", "here", "there",
        }
        words = re.findall(r"\b[a-zA-Z]{3,}\b", transcript)
        return [w.lower() for w in words if w.lower() not in stopwords][:10]

    def _detect_topic_shift(self, prev_text: str, current_text: str) -> bool:
        prev_words = set(prev_text.lower().split())
        curr_words = set(current_text.lower().split())
        if not prev_words or not curr_words:
            return False
        overlap = len(prev_words & curr_words) / max(len(prev_words | curr_words), 1)
        return overlap < 0.15

    def _update_health(self, success: bool):
        with self._lock:
            if not success:
                self._failures += 1
            total = self._total_calls
            failures = self._failures
        self._health_score = max(0.0, 1.0 - (failures / max(1, total)))
        if self._health_score < 0.3:
            self._status = ModelStatus.DEGRADED
