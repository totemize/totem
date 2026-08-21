"""Display state contracts shared by controllers and renderers.

The boot controller intentionally keeps its small legacy ``ScreenState``
contract.  Post-boot presentation consumes an orthogonal ``RuntimeSnapshot``
and projects it into one of the deliberately closed ``RuntimeScene`` values.
Keeping those two vocabularies separate prevents presentation concerns from
becoming another source of device state.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping, Optional, Tuple


class ScreenState(str, Enum):
    """High-level screen states; the boot POC implements a useful subset."""

    BOOTING = "booting"
    IDLE = "idle"
    NEW_PEER = "new_peer"
    EXISTING_PEER = "existing_peer"
    ERROR = "error"
    SYNCHRONIZING = "synchronizing"


@dataclass(frozen=True)
class ServiceStatus:
    key: str
    label: str
    ready: bool = False


@dataclass(frozen=True)
class ScreenFrame:
    state: ScreenState
    headline: str = ""
    services: Tuple[ServiceStatus, ...] = ()


class RuntimeScene(str, Enum):
    """The complete, closed post-boot scene vocabulary."""

    ALONE_IDLE = "alone_idle"
    PEER_SEEN = "peer_seen"
    CANDIDATE = "candidate"
    NEWLY_RECOGNIZED = "newly_recognized"
    RETURNING_RECOGNIZED = "returning_recognized"
    SYNC_RUNNING = "sync_running"
    SYNC_SUCCEEDED = "sync_succeeded"
    SYNC_INTERRUPTED = "sync_interrupted"
    NON_TOTEM_PEER = "non_totem_peer"
    CHARGING = "charging"
    LOW_BATTERY = "low_battery"
    CRITICAL_BATTERY = "critical_battery"
    MESH_DEGRADED = "mesh_degraded"


# These strings are product copy.  They are centralized so the projector,
# renderer, replay command, and contract tests cannot silently drift apart.
SCENE_SEQUENCES = {
    RuntimeScene.ALONE_IDLE: (
        "(•‿•)",
        "(◐‿◐)",
        "(•‿•)",
        "(◓‿◓)",
        "(•‿•)",
        "(◑‿◑)",
        "(•‿•)",
        "(◒‿◒)",
        "(-‿-)",
        "(•‿•)",
    ),
    RuntimeScene.PEER_SEEN: ("(•o•)!", "(•_•)?"),
    RuntimeScene.CANDIDATE: (
        "(•‿•)",
        "(˵•‿•˵)",
        "(˵•‿-)✧",
        "(˵•‿•˵)",
    ),
    RuntimeScene.NEWLY_RECOGNIZED: ("\\(★‿★)/",),
    RuntimeScene.RETURNING_RECOGNIZED: ("(ﾉ◕ヮ◕)ﾉ",),
    RuntimeScene.SYNC_RUNNING: (
        "(•‿•)•→(•_•)",
        "(•‿•)→•(•o•)",
        "(•ᴗ•)⇄(•ᴗ•)",
        "(•o•)•←(•‿•)",
        "(•_•)←•(•‿•)",
        "(•ᴗ•)⇄(•ᴗ•)",
    ),
    RuntimeScene.SYNC_SUCCEEDED: ("(✓‿✓)",),
    RuntimeScene.SYNC_INTERRUPTED: ("(´‿)ﾉ",),
    RuntimeScene.NON_TOTEM_PEER: (
        "(•_•)",
        "(¬_¬)",
        "( •_•)>⌐■-■",
        "(⌐■_■)",
        "(⌐■_■) ?",
        "( •_•)>⌐■-■",
        "(•_•)",
    ),
    RuntimeScene.CHARGING: (
        "(•‿•)⚡",
        "(•ᴗ•)⚡",
        "(◕‿◕)⚡",
        "(•ω•)⚡",
        "(•ᴗ•)⚡",
        "(•‿•)⚡",
    ),
    RuntimeScene.LOW_BATTERY: ("(－_－) zz", "(=_=)", "(－_－) zz"),
    RuntimeScene.CRITICAL_BATTERY: ("(×_×) !",),
    RuntimeScene.MESH_DEGRADED: ("(•_•)⌁", "(•‿•)⌁", "(•_•)⌁"),
}


# Captions are presentation copy, not state.  The runtime chooses one only when
# an authoritative scene admission begins and holds it until that admission
# ends.  Keeping the closed catalogue beside the face catalogue makes drift
# visible in tests and deterministic proof output.
SCENE_CAPTIONS = {
    RuntimeScene.ALONE_IDLE: (
        "nothing moved. i checked.",
        "nobody here. suspicious.",
        "supervising the empty.",
        "practicing peripheral vision.",
        "silence: fully operational.",
        "counting invisible guests.",
        "all quiet. too organized.",
        "alone, statistically.",
        "the room remains undefeated.",
        "just me and the air.",
    ),
    RuntimeScene.PEER_SEEN: (
        "the silence has an address.",
        "a signal cleared its throat.",
        "something joined the weather.",
        "the air brought company.",
        "nearby just got specific.",
        "someone pinged the void.",
        "the room gained a pulse.",
        "company, via atmosphere.",
        "a stranger in the static.",
        "the air blinked first.",
    ),
    RuntimeScene.CANDIDATE: (
        "oh. nice bandwidth.",
        "your latency suits you.",
        "well. aren't you well-routed.",
        "cute keys. keep talking.",
        "you make mesh look good.",
        "your packets have dimples.",
        "strong signal. nice face.",
        "that's a charming npub.",
        "you seem worth a retry.",
        "care to lose a packet?",
    ),
    RuntimeScene.NEWLY_RECOGNIZED: (
        "officially interesting.",
        "filed under: keep.",
        "you may enter the lore.",
        "friendship checksum passed.",
        "weirdness accepted.",
        "you've joined the plot.",
        "the handshake has a sequel.",
        "known, in the good way.",
        "one of us, approximately.",
        "recognition suits you.",
    ),
    RuntimeScene.RETURNING_RECOGNIZED: (
        "my favorite recurring signal.",
        "ah. a known variable.",
        "same weird. excellent.",
        "familiar static. good.",
        "the plot remembers you.",
        "still you. reassuring.",
        "recognized at first packet.",
        "back in local orbit.",
        "your chair is still imaginary.",
        "you again. statistically delightful.",
    ),
    RuntimeScene.SYNC_RUNNING: (
        "comparing secret handwriting…",
        "trading pocket universes…",
        "aligning our footnotes…",
        "passing notes through the air…",
        "finding what each missed…",
        "our margins are talking…",
        "quietly swapping context…",
        "notes in diplomatic transit…",
        "reconciling tiny histories…",
        "shuffling mutual evidence…",
    ),
    RuntimeScene.SYNC_SUCCEEDED: (
        "our margins agree.",
        "same gossip. fewer gaps.",
        "the footnotes shook hands.",
        "both sides remember.",
        "differences politely resolved.",
        "the missing bits arrived.",
        "mutual context achieved.",
        "our archives are speaking.",
        "nothing left in transit.",
        "we know what we know.",
    ),
    RuntimeScene.SYNC_INTERRUPTED: (
        "the air dropped a sentence.",
        "we were saying?",
        "conversation misplaced.",
        "weather ate the ending.",
        "the middle went missing.",
        "the signal changed its mind.",
        "unfinished, not forgotten.",
        "the air kept a souvenir.",
        "physics declined to comment.",
        "resume when weather permits.",
    ),
    RuntimeScene.NON_TOTEM_PEER: (
        "those glasses prove nothing.",
        "wrong handshake. nice disguise.",
        "nice try, mysterious appliance.",
        "not a totem. stylish, though.",
        "credentials: mostly sunglasses.",
        "the vibe lacks a signature.",
        "incognito is not identity.",
        "suspicion level: accessorized.",
        "all glasses, no proof.",
        "that handshake wore gloves.",
    ),
    RuntimeScene.CHARGING: (
        "electrons, à la carte.",
        "drinking organized lightning.",
        "domestic lightning. lovely.",
        "plugged into civilization.",
        "conducting a tiny feast.",
        "currently voltage-curious.",
        "eating from the wall.",
        "refilling the mischief.",
        "complimentary electrons!",
        "power, with table service.",
    ),
    RuntimeScene.LOW_BATTERY: (
        "thinking in lowercase.",
        "budgeting my eyebrows.",
        "small thoughts only.",
        "operating on implication.",
        "choosing my blinks carefully.",
        "running on punctuation.",
        "keeping ideas pocket-sized.",
        "conserving vowels.",
        "short sentences, please.",
        "essential mischief only.",
    ),
    RuntimeScene.CRITICAL_BATTERY: (
        "no long words, please.",
        "one blink. no promises.",
        "vowels now optional.",
        "please abbreviate everything.",
        "emergency punctuation only.",
        "barely enough for this face.",
        "power is now theoretical.",
        "using reserve eyebrows.",
        "one percent. full dignity.",
        "tell my notes i—",
    ),
    RuntimeScene.MESH_DEGRADED: (
        "the neighborhood is mumbling.",
        "everyone sounds far away.",
        "static has opinions.",
        "the air forgot some names.",
        "neighbors speaking in ellipses.",
        "the mesh misplaced a street.",
        "signals wearing fog.",
        "routes are feeling interpretive.",
        "the air needs a map.",
        "connectivity, now impressionist.",
    ),
}


@dataclass(frozen=True)
class AnimationReaction:
    """A bounded optional frame inserted into a deterministic base loop."""

    name: str
    expression: str
    dwell_seconds: float
    probability: float = 0.0


CHARGING_CENTER_EXPRESSION = "(•‿•)⚡"
CHARGING_REACTIONS = (
    AnimationReaction("blink", "(-‿-)⚡", 2.0, 0.20),
    AnimationReaction("glance", "(◑‿◑)⚡", 4.0, 0.10),
)
CHARGING_FULL_REACTION = AnimationReaction("full", "(★‿★)⚡", 10.0)


def replay_sequence(scene: RuntimeScene) -> Tuple[str, ...]:
    """Return every frame an operator must be able to proof deterministically."""

    sequence = SCENE_SEQUENCES[scene]
    if scene != RuntimeScene.CHARGING:
        return sequence
    return (
        sequence
        + tuple(reaction.expression for reaction in CHARGING_REACTIONS)
        + (CHARGING_FULL_REACTION.expression,)
    )


@dataclass(frozen=True)
class PowerSnapshot:
    """Normalized facts from the device-manager UPS route."""

    available: bool = False
    battery_percent: Optional[float] = None
    power_plugged: Optional[bool] = None


@dataclass(frozen=True)
class PeerSnapshot:
    """The presentation-relevant part of one authoritative peer row."""

    npub: str
    encounter: int = 0
    probe_verdict: Optional[str] = None
    recognized: bool = False
    known_before: bool = False
    sync_state: Optional[str] = None
    sync_attempt: Optional[int] = None
    present: bool = True


@dataclass(frozen=True)
class RuntimeSnapshot:
    """Orthogonal state axes reconciled from totemd and DeviceManager."""

    device_name: str = "TOTEM"
    fips_connected: bool = False
    mesh_size: int = 0
    peer_count: int = 0
    recognized_count: int = 0
    note_count: Optional[int] = None
    power: PowerSnapshot = field(default_factory=PowerSnapshot)
    peers: Tuple[PeerSnapshot, ...] = ()
    device_managers: int = 0
    event_counts: Tuple[Tuple[str, int], ...] = ()


@dataclass(frozen=True)
class RuntimeFrame:
    """A single exact sequence frame plus its current persistent badges."""

    scene: RuntimeScene
    expression: str
    sequence_index: int
    snapshot: RuntimeSnapshot
    caption: str = ""
    caption_word_count: int = 0


@dataclass(frozen=True)
class SceneSpec:
    """Scheduling policy for one presentation scene."""

    priority: int
    frame_seconds: float
    minimum_dwell: float
    transient: bool = False
    loop: bool = True


DEFAULT_SCENE_SPECS: Mapping[RuntimeScene, SceneSpec] = {
    RuntimeScene.CRITICAL_BATTERY: SceneSpec(100, 30.0, 30.0),
    RuntimeScene.NEWLY_RECOGNIZED: SceneSpec(70, 4.0, 4.0, True),
    RuntimeScene.RETURNING_RECOGNIZED: SceneSpec(70, 4.0, 4.0, True),
    RuntimeScene.SYNC_RUNNING: SceneSpec(60, 3.0, 9.0),
    RuntimeScene.SYNC_SUCCEEDED: SceneSpec(50, 4.0, 4.0, True),
    RuntimeScene.SYNC_INTERRUPTED: SceneSpec(50, 4.0, 4.0, True),
    RuntimeScene.CANDIDATE: SceneSpec(45, 3.0, 3.0, loop=False),
    RuntimeScene.PEER_SEEN: SceneSpec(40, 2.0, 4.0),
    RuntimeScene.LOW_BATTERY: SceneSpec(35, 12.0, 12.0),
    RuntimeScene.NON_TOTEM_PEER: SceneSpec(30, 6.0, 18.0),
    RuntimeScene.CHARGING: SceneSpec(20, 10.0, 30.0),
    RuntimeScene.MESH_DEGRADED: SceneSpec(15, 12.0, 12.0),
    RuntimeScene.ALONE_IDLE: SceneSpec(10, 12.0, 60.0),
}
