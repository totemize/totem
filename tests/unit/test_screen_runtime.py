"""BDD-style contracts for the continuous Totem screen projection."""

import asyncio
import hashlib
import json
from pathlib import Path
import re
import tempfile

from PIL import Image, ImageChops, ImageDraw
import pytest

from totem.screen.__main__ import _parser
from totem.screen.controller import ScreenController
from totem.screen.display import DeviceManagerDisplay
from totem.screen.model import (
    CHARGING_FULL_REACTION,
    CHARGING_REACTIONS,
    SCENE_CAPTIONS,
    SCENE_SEQUENCES,
    PeerSnapshot,
    PowerSnapshot,
    RuntimeFrame,
    RuntimeScene,
    RuntimeSnapshot,
    replay_sequence,
)
from totem.screen.render import (
    CAPTION_FONT_SIZE,
    CAPTION_FOOTER_GAP,
    CAPTION_MIN_FONT_SIZE,
    FALLBACK_PERSISTENT_TEXT_STROKE,
    FONT_BOLD_CANDIDATES,
    PERSISTENT_ICON_STROKE,
    FrameRenderer,
    VectorKaomoji,
)
from totem.screen.readiness import SERVICE_SPECS, SyntheticReadinessMonitor
from totem.screen.runtime import (
    CaptionAnimator,
    ProjectionEngine,
    RuntimeController,
    RuntimePolicy,
    RuntimeSource,
    SceneAnimator,
    SceneArbitrator,
    SourceUpdate,
    TotemSnapshotClient,
    TotemdBus,
    TotemdEventStream,
    synthetic_snapshot,
)

pytestmark = [pytest.mark.unit, pytest.mark.mock_transport]


EXPECTED_SEQUENCES = {
    RuntimeScene.IDLE: (
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

EXPECTED_CHARGING_REACTIONS = (
    "(-‿-)⚡",
    "(◑‿◑)⚡",
    "(★‿★)⚡",
)

EXPECTED_CAPTION_CATALOG_SHA256 = (
    "19202dbd508a2188a664fd871617baf0a4629450a08affcc828fd5de15f2e80b"
)


def _snapshot(
    *peers,
    fips_connected=True,
    battery=None,
    plugged=None,
    name="motown",
    notes=404,
):
    power = (
        PowerSnapshot(True, float(battery), plugged)
        if battery is not None
        else PowerSnapshot()
    )
    return RuntimeSnapshot(
        device_name=name,
        fips_connected=fips_connected,
        mesh_size=1193,
        peer_count=sum(peer.present for peer in peers),
        recognized_count=sum(peer.present and peer.recognized for peer in peers),
        note_count=notes,
        power=power,
        peers=tuple(peers),
    )


def _scene(snapshot, *, seed=False):
    projector = ProjectionEngine(RuntimePolicy(coalesce_seconds=0))
    if seed:
        projector.seed(snapshot)
    return projector.select(snapshot).scene


def _content_ink_bounds(image):
    content = image.crop((0, 22, image.width, image.height - 21))
    background = Image.new("1", content.size, 255)
    return ImageChops.difference(content, background).getbbox()


def _ink_bounds(image):
    return ImageChops.difference(image, Image.new("1", image.size, 255)).getbbox()


def _ink_count(image):
    return sum(pixel == 0 for pixel in image.getdata())


def test_given_the_product_catalog_when_loaded_then_only_exact_sequences_exist():
    """Given the catalog, when loaded, then every expression is exact."""

    assert set(RuntimeScene) == set(EXPECTED_SEQUENCES)
    assert SCENE_SEQUENCES == EXPECTED_SEQUENCES
    assert replay_sequence(RuntimeScene.CHARGING) == (
        EXPECTED_SEQUENCES[RuntimeScene.CHARGING] + EXPECTED_CHARGING_REACTIONS
    )


def test_given_caption_catalog_when_loaded_then_every_exact_option_is_present():
    """Given approved copy, when loaded, then no scene or phrase can drift."""

    assert set(SCENE_CAPTIONS) == set(RuntimeScene)
    assert all(len(SCENE_CAPTIONS[scene]) == 10 for scene in RuntimeScene)
    assert sum(len(options) for options in SCENE_CAPTIONS.values()) == 140
    payload = json.dumps(
        [[scene.value, list(SCENE_CAPTIONS[scene])] for scene in RuntimeScene],
        ensure_ascii=False,
        separators=(",", ":"),
    )
    assert hashlib.sha256(payload.encode("utf-8")).hexdigest() == (
        EXPECTED_CAPTION_CATALOG_SHA256
    )
    assert all(
        replay_sequence(scene) == sequence
        for scene, sequence in EXPECTED_SEQUENCES.items()
        if scene != RuntimeScene.CHARGING
    )


@pytest.mark.parametrize(
    "scene,index,expression",
    [
        (scene, index, expression)
        for scene in RuntimeScene
        for sequence in (replay_sequence(scene),)
        for index, expression in enumerate(sequence)
    ],
)
def test_given_each_exact_frame_when_rendered_then_vector_ink_is_visible(
    scene, index, expression
):
    """Given every frame, when rendered, then no external glyph is needed."""

    assert VectorKaomoji.supports(expression)
    image = FrameRenderer().render_runtime(
        RuntimeFrame(scene, expression, index, synthetic_snapshot("motown"))
    )

    assert image.mode == "1"
    assert image.size == (250, 122)
    bounds = _content_ink_bounds(image)
    assert bounds is not None
    assert 8 <= bounds[0] < bounds[2] <= image.width - 8
    assert bounds[1] >= 0
    assert bounds[3] <= 79
    if scene == RuntimeScene.NON_TOTEM_PEER:
        assert bounds[0] == 8
    else:
        assert abs((bounds[0] + bounds[2]) / 2 - image.width / 2) <= 4


def test_given_suspicious_animation_when_props_move_then_face_origin_stays_left():
    """Given glasses motion, when frames change, then the face does not drift."""

    renderer = FrameRenderer()
    origins = []
    heights = []
    for index, expression in enumerate(replay_sequence(RuntimeScene.NON_TOTEM_PEER)):
        image = renderer.render_runtime(
            RuntimeFrame(
                RuntimeScene.NON_TOTEM_PEER,
                expression,
                index,
                synthetic_snapshot("metot"),
            )
        )
        bounds = _content_ink_bounds(image)
        assert bounds is not None
        origins.append(bounds[0])
        heights.append(bounds[3] - bounds[1])

    assert origins == [8] * len(origins)
    assert len(set(heights)) == 1


def test_given_every_animation_frame_then_persistent_chrome_never_moves():
    """Given animation, when expressions change, then chrome bytes stay exact."""

    renderer = FrameRenderer()
    snapshot = synthetic_snapshot("metot")
    chrome = None
    for scene in RuntimeScene:
        for index, expression in enumerate(replay_sequence(scene)):
            image = renderer.render_runtime(
                RuntimeFrame(scene, expression, index, snapshot)
            )
            sample = (
                image.crop((0, 0, image.width, 22)).tobytes()
                + image.crop((0, 101, image.width, image.height)).tobytes()
            )
            if chrome is None:
                chrome = sample
            assert sample == chrome


def test_given_runtime_facts_when_rendered_then_layout_contract_is_stable():
    """Given facts, when rendered, then header/content/footer stay distinct."""

    snapshot = RuntimeSnapshot(
        device_name="motown",
        fips_connected=True,
        mesh_size=1193,
        peer_count=4,
        recognized_count=2,
        note_count=404,
        power=PowerSnapshot(True, 75.0, False),
    )
    renderer = FrameRenderer()
    image = renderer.render_runtime(
        RuntimeFrame(RuntimeScene.ALONE_IDLE, "(•‿•)", 0, snapshot)
    )

    # Name ink is left; FIPS and battery vector ink are right, battery rightmost.
    assert _ink_bounds(image.crop((0, 0, 170, 20))) is not None
    assert _ink_bounds(image.crop((190, 0, 218, 20))) is not None
    assert _ink_bounds(image.crop((219, 0, 250, 20))) is not None
    assert renderer.footer_counts(snapshot) == (1193, 4, 2, 404)
    assert renderer.footer_text(snapshot) == "1193 / 4 / 2 / 404"
    assert _ink_bounds(image.crop((0, 104, 170, 122))) is not None
    assert _ink_bounds(image.crop((205, 104, 250, 122))) is not None

    icons = []
    for icon in (
        renderer._mesh_count_icon,
        renderer._peer_count_icon,
        renderer._recognized_count_icon,
        renderer._note_count_icon,
    ):
        canvas = Image.new("1", (16, 16), 255)
        icon(ImageDraw.Draw(canvas), 2, 2)
        icons.append(canvas.tobytes())
    assert len(set(icons)) == 4

    friend_icon = Image.new("1", (16, 16), 255)
    renderer._recognized_count_icon(ImageDraw.Draw(friend_icon), 2, 2)
    # Exact [•] construction: square-bracket stems around a filled dot.
    assert friend_icon.getpixel((3, 4)) == 0
    assert friend_icon.getpixel((9, 7)) == 0
    assert friend_icon.getpixel((14, 4)) == 0


def test_given_note_count_is_unknown_then_footer_does_not_invent_zero():
    snapshot = RuntimeSnapshot(note_count=None)
    renderer = FrameRenderer()

    assert renderer.footer_counts(snapshot)[-1] is None
    assert renderer.footer_text(snapshot).endswith(" / ?")


def test_given_all_captions_and_prefixes_when_rendered_then_the_band_is_safe():
    """Given approved copy, when revealed, then it stays fixed and separated."""

    renderer = FrameRenderer()
    snapshot = synthetic_snapshot("metot")
    footer_top = renderer.height - 20
    caption_bounds = renderer._caption_bounds(footer_top)
    assert caption_bounds[3] == footer_top - CAPTION_FOOTER_GAP

    for scene in RuntimeScene:
        expression = SCENE_SEQUENCES[scene][0]
        for caption in SCENE_CAPTIONS[scene]:
            origin = None
            for visible_words in range(1, len(caption.split()) + 1):
                frame = RuntimeFrame(
                    scene,
                    expression,
                    0,
                    snapshot,
                    caption,
                    visible_words,
                )
                image = renderer.render_runtime(frame)
                assert image.mode == "1"
                assert image.size == (250, 122)
                caption_ink = _ink_bounds(image.crop(caption_bounds))
                assert caption_ink is not None
                assert caption_ink[1] >= 0
                assert caption_ink[3] <= caption_bounds[3] - caption_bounds[1]
                if origin is None:
                    origin = caption_ink[0]
                assert caption_ink[0] == origin

                current_face = image.crop((0, 21, image.width, caption_bounds[1]))
                current_footer = image.crop((0, footer_top, image.width, image.height))
                if visible_words > 1:
                    previous = renderer.render_runtime(
                        RuntimeFrame(
                            scene,
                            expression,
                            0,
                            snapshot,
                            caption,
                            visible_words - 1,
                        )
                    )
                    assert (
                        current_face.tobytes()
                        == previous.crop(
                            (0, 21, image.width, caption_bounds[1])
                        ).tobytes()
                    )
                    assert (
                        current_footer.tobytes()
                        == previous.crop(
                            (0, footer_top, image.width, image.height)
                        ).tobytes()
                    )

            draw = ImageDraw.Draw(Image.new("1", (250, 122), 255))
            font, _, _, ink = renderer._caption_layout(draw, caption, caption_bounds)
            assert CAPTION_MIN_FONT_SIZE <= font.size <= CAPTION_FONT_SIZE
            assert caption_bounds[0] <= ink[0] < ink[2] <= caption_bounds[2]
            assert caption_bounds[1] <= ink[1] < ink[3] <= caption_bounds[3]

    # The reserved clearance above the footer rule contains no caption ink.
    sample = renderer.render_runtime(
        RuntimeFrame(
            RuntimeScene.ALONE_IDLE,
            SCENE_SEQUENCES[RuntimeScene.ALONE_IDLE][0],
            0,
            snapshot,
            SCENE_CAPTIONS[RuntimeScene.ALONE_IDLE][0],
            4,
        )
    )
    assert _ink_bounds(sample.crop((0, caption_bounds[3], 250, footer_top))) is None


def test_given_persistent_chrome_when_rendered_then_normal_bold_is_balanced():
    """Given tiny chrome, when drawn, then real bold needs no extra-black stroke."""

    renderer = FrameRenderer()
    installed_bold = next(
        (path for path in FONT_BOLD_CANDIDATES if Path(path).is_file()), None
    )
    assert all("black" not in Path(path).name.lower() for path in FONT_BOLD_CANDIDATES)
    assert renderer.bold_font_path == installed_bold
    if installed_bold is not None:
        assert any(
            weight in Path(installed_bold).name.lower() for weight in ("bold", "heavy")
        )
        assert "black" not in Path(installed_bold).name.lower()

    bold_font = renderer._font(13, bold=True)
    regular_font = renderer._font(13)
    bold_sample = Image.new("1", (170, 20), 255)
    regular_sample = Image.new("1", (170, 20), 255)
    ImageDraw.Draw(bold_sample).text((5, 0), "metot", font=bold_font, fill=0)
    ImageDraw.Draw(regular_sample).text((5, 0), "metot", font=regular_font, fill=0)
    frame = RuntimeFrame(
        RuntimeScene.ALONE_IDLE,
        "(•‿•)",
        0,
        synthetic_snapshot("metot"),
    )
    rendered = renderer.render_runtime(frame)
    header_name = rendered.crop((0, 0, 170, 20))

    assert PERSISTENT_ICON_STROKE == 1
    if installed_bold is not None:
        assert renderer.persistent_text_stroke == 0
        assert _ink_count(bold_sample) > _ink_count(regular_sample) * 1.1
        assert _ink_count(header_name) == _ink_count(bold_sample)
    else:
        assert renderer.persistent_text_stroke == FALLBACK_PERSISTENT_TEXT_STROKE
        assert _ink_count(header_name) > _ink_count(bold_sample)
    assert _ink_count(rendered.crop((4, 20, 246, 21))) == 242
    assert _ink_count(rendered.crop((4, 21, 246, 22))) == 0
    assert _ink_count(rendered.crop((4, 102, 246, 103))) == 242
    assert _ink_count(rendered.crop((4, 103, 246, 104))) == 0

    # If a bold face is missing, bold requests still fall back to the regular
    # installed face (or Pillow's built-in face) plus synthetic stroke weight.
    renderer.bold_font_path = None
    fallback_font = renderer._font(11, bold=True)
    unweighted = Image.new("1", (170, 20), 255)
    weighted = Image.new("1", (170, 20), 255)
    ImageDraw.Draw(unweighted).text((5, 0), "metot", font=fallback_font, fill=0)
    renderer._draw_persistent_text(
        ImageDraw.Draw(weighted), (5, 0), "metot", fallback_font
    )
    assert renderer.persistent_text_stroke == FALLBACK_PERSISTENT_TEXT_STROKE == 1
    assert _ink_count(weighted) > _ink_count(unweighted)


@pytest.mark.parametrize("percent", (15.0, 100.0))
def test_given_external_power_then_battery_badge_is_visible_at_every_fill(percent):
    """Given low or full charge, when plugged, then vector ink still differs."""

    renderer = FrameRenderer()
    unplugged = _snapshot(battery=percent, plugged=False)
    plugged = _snapshot(battery=percent, plugged=True)
    expression = SCENE_SEQUENCES[RuntimeScene.LOW_BATTERY][0]
    without_badge = renderer.render_runtime(
        RuntimeFrame(RuntimeScene.LOW_BATTERY, expression, 0, unplugged)
    )
    with_badge = renderer.render_runtime(
        RuntimeFrame(RuntimeScene.LOW_BATTERY, expression, 0, plugged)
    )

    assert (
        ImageChops.difference(
            without_badge.crop((219, 0, 250, 20)),
            with_badge.crop((219, 0, 250, 20)),
        ).getbbox()
        is not None
    )


def test_given_a_rotated_mount_when_rendered_then_the_complete_ui_rotates():
    """Given 180-degree mounting, when rendered, then all layers rotate."""

    frame = RuntimeFrame(
        RuntimeScene.SYNC_SUCCEEDED,
        "(✓‿✓)",
        0,
        synthetic_snapshot("metot"),
    )
    upright = FrameRenderer().render_runtime(frame)
    mounted = FrameRenderer(rotation=180).render_runtime(frame)

    assert mounted.tobytes() == upright.rotate(180).tobytes()


SCENE_CASES = (
    (_snapshot(), RuntimeScene.ALONE_IDLE),
    (_snapshot(PeerSnapshot("seen", 1)), RuntimeScene.PEER_SEEN),
    (
        _snapshot(PeerSnapshot("candidate", 1, probe_verdict="candidate")),
        RuntimeScene.CANDIDATE,
    ),
    (
        _snapshot(PeerSnapshot("new", 1, recognized=True, known_before=False)),
        RuntimeScene.NEWLY_RECOGNIZED,
    ),
    (
        _snapshot(PeerSnapshot("old", 2, recognized=True, known_before=True)),
        RuntimeScene.RETURNING_RECOGNIZED,
    ),
    (
        _snapshot(PeerSnapshot("sync", 1, sync_state="running")),
        RuntimeScene.SYNC_RUNNING,
    ),
    (
        _snapshot(PeerSnapshot("sync", 1, sync_state="succeeded", sync_attempt=2)),
        RuntimeScene.SYNC_SUCCEEDED,
    ),
    (
        _snapshot(PeerSnapshot("sync", 1, sync_state="timed_out", sync_attempt=2)),
        RuntimeScene.SYNC_INTERRUPTED,
    ),
    (
        _snapshot(PeerSnapshot("sync", 1, sync_state="cancelled", sync_attempt=2)),
        RuntimeScene.SYNC_INTERRUPTED,
    ),
    (
        _snapshot(PeerSnapshot("other", 1, probe_verdict="not_totem")),
        RuntimeScene.NON_TOTEM_PEER,
    ),
    (_snapshot(battery=75, plugged=True), RuntimeScene.CHARGING),
    (_snapshot(battery=15, plugged=False), RuntimeScene.LOW_BATTERY),
    (_snapshot(battery=5, plugged=False), RuntimeScene.CRITICAL_BATTERY),
    (_snapshot(fips_connected=False), RuntimeScene.MESH_DEGRADED),
)


@pytest.mark.parametrize("snapshot,expected", SCENE_CASES)
def test_given_each_authoritative_scenario_when_projected_then_scene_is_exact(
    snapshot, expected
):
    """Given every state scenario, when projected, then its exact scene wins."""

    assert _scene(snapshot) == expected


def test_given_unsupported_probe_and_sync_results_then_no_extra_scene_is_invented():
    """Given signals outside scope, when projected, then ambient remains."""

    snapshot = _snapshot(
        PeerSnapshot("peer", 1, probe_verdict="unreachable", sync_state="failed")
    )

    assert _scene(snapshot) == RuntimeScene.ALONE_IDLE


def test_given_online_friend_after_payoffs_then_neutral_idle_replaces_lonely_idle():
    """Given present recognized company, ambient copy must not claim loneliness."""

    snapshot = _snapshot(
        PeerSnapshot("unreachable-a", 1, probe_verdict="unreachable"),
        PeerSnapshot("unreachable-b", 1, probe_verdict="unreachable"),
        PeerSnapshot(
            "friend-a",
            7,
            probe_verdict="candidate",
            recognized=True,
            known_before=True,
            sync_state="succeeded",
            sync_attempt=3,
        ),
        PeerSnapshot(
            "friend-b",
            4,
            probe_verdict="candidate",
            recognized=True,
            known_before=True,
            sync_state="succeeded",
            sync_attempt=2,
        ),
    )
    projector = ProjectionEngine(RuntimePolicy(coalesce_seconds=0))
    projector.seed(snapshot)

    assert (snapshot.peer_count, snapshot.recognized_count) == (4, 2)
    assert projector.select(snapshot).scene == RuntimeScene.IDLE

    departed = _snapshot(
        PeerSnapshot(
            "friend",
            7,
            recognized=True,
            known_before=True,
            present=False,
        )
    )
    assert projector.select(departed).scene == RuntimeScene.ALONE_IDLE


def test_given_departed_tombstone_then_only_cancelled_payoff_is_projected():
    """Given a departed row, when projected, then it cannot masquerade as live."""

    departed = PeerSnapshot(
        "peer",
        7,
        probe_verdict="candidate",
        recognized=True,
        known_before=True,
        sync_state="cancelled",
        sync_attempt=3,
        present=False,
    )
    snapshot = _snapshot(departed)
    projector = ProjectionEngine(RuntimePolicy(coalesce_seconds=0))
    choice = projector.select(snapshot)

    assert (snapshot.peer_count, snapshot.recognized_count) == (0, 0)
    assert choice.scene == RuntimeScene.SYNC_INTERRUPTED
    projector.mark_presented(choice)
    assert projector.select(snapshot).scene == RuntimeScene.ALONE_IDLE

    not_cancelled = _snapshot(
        PeerSnapshot(
            "peer",
            7,
            probe_verdict="not_totem",
            recognized=True,
            sync_state="running",
            present=False,
        )
    )
    assert _scene(not_cancelled) == RuntimeScene.ALONE_IDLE


def test_given_competing_axes_when_projected_then_priority_is_deterministic():
    """Given compound state, when projected, then priority preserves all axes."""

    new_sync = PeerSnapshot(
        "peer",
        1,
        probe_verdict="candidate",
        recognized=True,
        known_before=False,
        sync_state="running",
    )
    assert _scene(_snapshot(new_sync, battery=75, plugged=True)) == (
        RuntimeScene.NEWLY_RECOGNIZED
    )
    assert _scene(_snapshot(new_sync, battery=5, plugged=True)) == (
        RuntimeScene.CRITICAL_BATTERY
    )
    assert _scene(_snapshot(battery=15, plugged=True)) == RuntimeScene.LOW_BATTERY


def test_given_startup_snapshot_when_seeded_then_stale_payoffs_are_not_replayed():
    """Given restart, when seeded, then old terminal/social scenes are consumed."""

    initial = _snapshot(
        PeerSnapshot(
            "peer",
            1,
            recognized=True,
            known_before=True,
            sync_state="succeeded",
            sync_attempt=4,
        )
    )
    projector = ProjectionEngine(RuntimePolicy(coalesce_seconds=0))
    projector.seed(initial)

    assert projector.select(initial).scene == RuntimeScene.IDLE
    next_encounter = _snapshot(
        PeerSnapshot("peer", 2, recognized=True, known_before=True)
    )
    assert projector.select(next_encounter).scene == (RuntimeScene.RETURNING_RECOGNIZED)


def test_given_a_presented_terminal_result_when_polled_then_it_is_one_shot():
    """Given a terminal result, when presented and polled, then it does not loop."""

    snapshot = _snapshot(
        PeerSnapshot(
            "peer",
            1,
            probe_verdict="unreachable",
            sync_state="succeeded",
            sync_attempt=3,
        )
    )
    projector = ProjectionEngine(RuntimePolicy(coalesce_seconds=0))
    result = projector.select(snapshot)
    projector.mark_presented(result)

    assert result.scene == RuntimeScene.SYNC_SUCCEEDED
    assert projector.select(snapshot).scene == RuntimeScene.ALONE_IDLE


def test_given_burst_updates_when_arbitrated_then_the_latest_snapshot_is_coalesced():
    """Given seen/candidate burst, when quiet, then only candidate activates."""

    policy = RuntimePolicy(coalesce_seconds=2.0)
    arbitrator = SceneArbitrator(ProjectionEngine(policy), policy)
    arbitrator.submit(_snapshot(PeerSnapshot("peer", 1)), 0.0)
    assert arbitrator.resolve(1.0) is None
    arbitrator.submit(
        _snapshot(PeerSnapshot("peer", 1, probe_verdict="candidate")), 1.0
    )

    assert arbitrator.resolve(2.9) is None
    assert arbitrator.resolve(3.0).scene == RuntimeScene.CANDIDATE


def test_given_higher_priority_activity_then_ambient_dwell_does_not_block_it():
    """Given idle, when a peer arrives, then quiet-time—not idle dwell—governs."""

    policy = RuntimePolicy(coalesce_seconds=0)
    arbitrator = SceneArbitrator(ProjectionEngine(policy), policy)
    arbitrator.submit(_snapshot(), 0.0)
    assert arbitrator.resolve(0.0).scene == RuntimeScene.ALONE_IDLE
    arbitrator.submit(_snapshot(PeerSnapshot("peer", 1)), 1.0)

    assert arbitrator.resolve(1.0).scene == RuntimeScene.PEER_SEEN


def test_given_social_payoff_when_lower_priority_arrives_then_minimum_dwell_holds():
    """Given recognition, when sync follows, then payoff dwells before exchange."""

    policy = RuntimePolicy(coalesce_seconds=0)
    arbitrator = SceneArbitrator(ProjectionEngine(policy), policy)
    arbitrator.submit(_snapshot(), 0.0)
    assert arbitrator.resolve(0.0).scene == RuntimeScene.ALONE_IDLE
    recognized = PeerSnapshot("peer", 1, recognized=True, known_before=False)
    arbitrator.submit(_snapshot(recognized), 1.0)
    recognized_choice = arbitrator.resolve(1.0)
    assert recognized_choice.scene == RuntimeScene.NEWLY_RECOGNIZED
    arbitrator.mark_presented(recognized_choice)
    syncing = PeerSnapshot(
        "peer", 1, recognized=True, known_before=False, sync_state="running"
    )
    arbitrator.submit(_snapshot(syncing), 2.0)

    assert arbitrator.resolve(3.9).scene == RuntimeScene.NEWLY_RECOGNIZED
    assert arbitrator.resolve(5.0).scene == RuntimeScene.SYNC_RUNNING


def test_given_one_frame_persistent_scene_then_transition_has_a_wake_deadline():
    """Given candidate clears, when no push follows, then dwell ends on time."""

    policy = RuntimePolicy(coalesce_seconds=2.0)
    arbitrator = SceneArbitrator(ProjectionEngine(policy), policy)
    arbitrator.submit(
        _snapshot(PeerSnapshot("peer", 1, probe_verdict="candidate")), 0.0
    )
    assert arbitrator.resolve(2.0).scene == RuntimeScene.CANDIDATE
    arbitrator.submit(_snapshot(), 2.5)

    assert arbitrator.resolve(3.0).scene == RuntimeScene.CANDIDATE
    assert arbitrator.resolution_deadline() == 5.0
    assert arbitrator.resolve(5.0).scene == RuntimeScene.ALONE_IDLE


def test_given_many_simultaneous_peers_when_projected_then_queue_is_bounded():
    """Given a recognition crowd, when coalesced, then backlog stays bounded."""

    policy = RuntimePolicy(coalesce_seconds=0, maximum_pending_scenes=2)
    projector = ProjectionEngine(policy)
    snapshot = _snapshot(
        *(
            PeerSnapshot("peer{}".format(index), index, recognized=True)
            for index in range(6)
        )
    )

    choice = projector.select(snapshot)
    assert choice.scene == RuntimeScene.NEWLY_RECOGNIZED
    assert len(choice.tokens) == 2
    projector.mark_presented(choice)
    assert projector.select(snapshot).scene == RuntimeScene.IDLE


def test_given_departed_and_old_encounters_then_consumed_history_is_pruned():
    """Given a long-lived process, when peers advance, then dedupe stays bounded."""

    policy = RuntimePolicy(
        coalesce_seconds=0,
        maximum_pending_scenes=1,
        maximum_consumed_tokens=2,
    )
    projector = ProjectionEngine(policy)
    old = _snapshot(PeerSnapshot("peer", 1, recognized=True))
    choice = projector.select(old)
    projector.mark_presented(choice)
    assert len(projector._consumed) == 1

    # A newer encounter makes the old payoff token obsolete.
    projector.select(_snapshot(PeerSnapshot("peer", 2)))
    assert len(projector._consumed) == 0

    # Departure also removes all tokens for a peer no longer in authority.
    current = _snapshot(PeerSnapshot("peer", 2, recognized=True))
    projector.mark_presented(projector.select(current))
    projector.select(_snapshot())
    assert len(projector._consumed) == 0


class FakeBus:
    def __init__(self, status, peers):
        self.status = status
        self.peers = peers
        self.calls = []

    async def call(self, message_type):
        self.calls.append(message_type)
        if message_type == "totem.status.get":
            return {"ok": True, "status": self.status}
        return {"ok": True, "peers": self.peers}


class FakeDeviceManager:
    def __init__(self, ups=None, managers=None):
        self.ups = ups or {}
        self.managers = managers or []
        self.waited = False
        self.images = []
        self.refresh_modes = []

    async def ups_status(self):
        return self.ups

    async def health(self):
        return {"status": "healthy", "initialized_managers": self.managers}

    async def wait_ready(self, timeout=60.0):
        self.waited = True

    async def show(self, image, refresh_mode="full"):
        self.images.append(image.copy())
        self.refresh_modes.append(refresh_mode)


def test_given_both_authorities_when_fetched_then_snapshot_axes_are_normalized():
    """Given totemd and UPS, when fetched, then the snapshot preserves facts."""

    bus = FakeBus(
        {
            "config": {"device_name": "motown"},
            "fips": {"connected": True, "mesh_size": 1193},
            "peers": 4,
            "recognized": 2,
            "notes": 404,
            "events": {"totem.peer.seen": 4, "totem.sync.done": 2},
        },
        [
            {
                "npub": "npub1peer",
                "first_seen": 7,
                "probe_verdict": "candidate",
                "recognized": True,
                "known_before": False,
                "sync_state": "running",
                "sync_attempt": 3,
                "present": True,
            }
        ],
    )
    display = FakeDeviceManager(
        {
            "battery_percent": 97.6,
            "power_plugged": True,
            "current_amps": -0.366,
        },
        ["display", "ups"],
    )

    snapshot = asyncio.run(TotemSnapshotClient(bus, display).fetch())

    assert bus.calls == ["totem.status.get", "totem.peers.get"]
    assert snapshot.device_name == "motown"
    # Mesh remains status authority.  Direct/recognized counts stay coherent
    # with the one live peers.get row, even when status is from an older epoch.
    assert (snapshot.mesh_size, snapshot.peer_count, snapshot.recognized_count) == (
        1193,
        1,
        1,
    )
    assert snapshot.power == PowerSnapshot(True, 97.6, True)
    assert snapshot.note_count == 404
    assert snapshot.device_managers == 2
    assert snapshot.event_counts == (
        ("totem.peer.seen", 4),
        ("totem.sync.done", 2),
    )
    assert snapshot.peers == (
        PeerSnapshot(
            "npub1peer",
            7,
            "candidate",
            True,
            False,
            "running",
            3,
            True,
        ),
    )


def test_given_status_row_mismatch_then_footer_counts_use_the_same_live_peer_rows():
    """Given mixed epochs, when normalized, then scene and badges stay coherent."""

    bus = FakeBus(
        {
            "config": {"device_name": "motown"},
            "fips": {"connected": True, "mesh_size": 2},
            "peers": 99,
            "recognized": 98,
        },
        [
            {"npub": "live", "first_seen": 8, "recognized": True},
            {
                "npub": "gone",
                "first_seen": 7,
                "recognized": True,
                "sync_state": "cancelled",
                "present": False,
            },
        ],
    )

    snapshot = asyncio.run(TotemSnapshotClient(bus, FakeDeviceManager()).fetch())

    assert (snapshot.peer_count, snapshot.recognized_count) == (1, 1)
    assert tuple(peer.present for peer in snapshot.peers) == (True, False)


def test_given_unavailable_ups_when_fetched_then_control_plane_remains_usable():
    """Given optional UPS failure, when fetched, then it is an unknown badge."""

    bus = FakeBus(
        {
            "config": {"device_name": "metot"},
            "fips": {"connected": True, "mesh_size": 1},
            "peers": 0,
            "recognized": 0,
        },
        [],
    )
    snapshot = asyncio.run(TotemSnapshotClient(bus, FakeDeviceManager()).fetch())

    assert snapshot.power == PowerSnapshot()
    assert _scene(snapshot) == RuntimeScene.ALONE_IDLE


class FakeSnapshots:
    def __init__(self, snapshots):
        self.snapshots = list(snapshots)
        self.calls = 0

    async def fetch(self):
        value = self.snapshots[min(self.calls, len(self.snapshots) - 1)]
        self.calls += 1
        return value


class FakeEventStream:
    def __init__(self, events=(), connect_error=None, wait_forever=False):
        self.events = list(events)
        self.connect_error = connect_error
        self.wait_forever = wait_forever
        self.connected = 0
        self.closed = 0

    async def connect(self):
        self.connected += 1
        if self.connect_error:
            raise self.connect_error

    async def next_event(self):
        if self.events:
            return self.events.pop(0)
        if self.wait_forever:
            await asyncio.Event().wait()
        raise ConnectionError("done")

    async def close(self):
        self.closed += 1


def test_given_sse_notification_when_received_then_fresh_snapshot_is_authority():
    """Given a misleading push, when reconciled, then snapshot chooses scene."""

    idle = _snapshot()
    stream = FakeEventStream([{"type": "totem.recognized", "known_before": False}])
    source = RuntimeSource(
        FakeSnapshots([idle, idle]),
        stream_factory=lambda: stream,
        poll_seconds=60,
        reconnect_seconds=0,
    )

    async def scenario():
        updates = source.updates()
        first = await updates.__anext__()
        second = await updates.__anext__()
        await updates.aclose()
        return first, second

    first, second = asyncio.run(scenario())

    assert first.reconnected is True
    assert second.notification["type"] == "totem.recognized"
    assert _scene(second.snapshot) == RuntimeScene.ALONE_IDLE
    assert stream.closed == 1


def test_given_silent_sse_when_poll_elapses_then_snapshot_is_refreshed():
    """Given no pushes, when poll elapses, then UPS/FIPS facts still refresh."""

    first_snapshot = _snapshot(battery=80)
    second_snapshot = _snapshot(battery=79)
    stream = FakeEventStream(wait_forever=True)
    snapshots = FakeSnapshots([first_snapshot, second_snapshot])
    source = RuntimeSource(
        snapshots,
        stream_factory=lambda: stream,
        poll_seconds=0.001,
        reconnect_seconds=0,
    )

    async def scenario():
        updates = source.updates()
        first = await updates.__anext__()
        second = await updates.__anext__()
        await updates.aclose()
        return first, second

    first, second = asyncio.run(scenario())

    assert first.snapshot.power.battery_percent == 80
    assert second.notification is None
    assert second.snapshot.power.battery_percent == 79
    assert snapshots.calls == 2


def test_given_failed_sse_connect_when_retried_then_reconnect_snapshot_arrives():
    """Given disconnect, when retried, then a new stream reconciles first."""

    failed = FakeEventStream(connect_error=ConnectionError("offline"))
    recovered = FakeEventStream(wait_forever=True)
    streams = iter((failed, recovered))
    source = RuntimeSource(
        FakeSnapshots([_snapshot()]),
        stream_factory=lambda: next(streams),
        poll_seconds=60,
        reconnect_seconds=0,
    )

    async def scenario():
        updates = source.updates()
        update = await updates.__anext__()
        await updates.aclose()
        return update

    update = asyncio.run(scenario())

    assert update.reconnected is True
    assert failed.closed == 1
    assert recovered.connected == 1
    assert recovered.closed == 1


def test_given_connected_sse_reaches_eof_then_a_new_stream_reconciles_first():
    """Given live stream EOF, when reconnecting, then snapshot precedes events."""

    ended = FakeEventStream()
    recovered = FakeEventStream(wait_forever=True)
    streams = iter((ended, recovered))
    snapshots = FakeSnapshots([_snapshot(battery=80), _snapshot(battery=79)])
    source = RuntimeSource(
        snapshots,
        stream_factory=lambda: next(streams),
        poll_seconds=60,
        reconnect_seconds=0,
    )

    async def scenario():
        updates = source.updates()
        first = await updates.__anext__()
        second = await updates.__anext__()
        await updates.aclose()
        return first, second

    first, second = asyncio.run(scenario())

    assert first.snapshot.power.battery_percent == 80
    assert second.reconnected is True
    assert second.snapshot.power.battery_percent == 79
    assert ended.closed == 1
    assert recovered.closed == 1


@pytest.mark.parametrize(
    "line,expected",
    (
        (b"event:totem.peer.seen\n", None),
        (b":keep-alive\n", None),
        (b'data: {"type":"totem.peer.seen"}\n', {"type": "totem.peer.seen"}),
        (b'{"type":"totem.sync.started"}\n', {"type": "totem.sync.started"}),
        (b"not-json\n", None),
    ),
)
def test_given_totemctl_sse_lines_when_parsed_then_only_json_data_notifies(
    line, expected
):
    """Given SSE CLI output, when parsed, then event labels are ignored."""

    assert TotemdEventStream.parse_line(line) == expected


def test_given_custom_bus_url_then_poll_and_sse_use_the_same_authority():
    """Given an override, when wiring clients, then the SSE address is retained."""

    bus = TotemdBus("http://127.0.0.1:9123/bus")
    stream = TotemdEventStream(bus_address=bus.event_address)

    assert bus.event_address == "127.0.0.1:9123"
    assert stream.executable == "totemctl"
    assert stream.bus_address == "127.0.0.1:9123"


def test_given_rate_overrides_when_applied_then_each_sequence_is_configurable():
    """Given per-scene rates, when parsed, then only named scenes change."""

    policy = (
        RuntimePolicy()
        .with_frame_rates(("alone_idle=30", "sync_running=1.25"))
        .with_minimum_dwells(("newly_recognized=8",))
        .with_priorities(("charging=25",))
    )

    assert policy.scene_specs[RuntimeScene.ALONE_IDLE].frame_seconds == 30
    assert policy.scene_specs[RuntimeScene.SYNC_RUNNING].frame_seconds == 1.25
    assert policy.scene_specs[RuntimeScene.CHARGING].frame_seconds == 10
    assert policy.scene_specs[RuntimeScene.NEWLY_RECOGNIZED].minimum_dwell == 8
    assert policy.scene_specs[RuntimeScene.CHARGING].priority == 25


def test_given_interactive_scenes_then_exact_dwell_and_loop_policy_is_explicit():
    """Given approved motion, when scheduled, then timings match the contract."""

    specs = RuntimePolicy().scene_specs
    assert specs[RuntimeScene.ALONE_IDLE].frame_seconds == 12
    assert specs[RuntimeScene.CHARGING].frame_seconds == 10
    assert specs[RuntimeScene.SYNC_RUNNING].frame_seconds == 3
    assert specs[RuntimeScene.NON_TOTEM_PEER].frame_seconds == 6
    assert specs[RuntimeScene.CANDIDATE].frame_seconds == 3
    assert specs[RuntimeScene.CANDIDATE].loop is False
    assert tuple(
        (reaction.expression, reaction.dwell_seconds, reaction.probability)
        for reaction in CHARGING_REACTIONS
    ) == (("(-‿-)⚡", 2.0, 0.20), ("(◑‿◑)⚡", 4.0, 0.10))
    assert (
        CHARGING_FULL_REACTION.expression,
        CHARGING_FULL_REACTION.dwell_seconds,
    ) == ("(★‿★)⚡", 10.0)
    assert RuntimePolicy().caption_word_seconds == 1.2


def test_given_caption_admissions_then_selection_is_stable_and_non_repeating():
    """Given scene entries, when copy is chosen, then one admission holds it."""

    calls = []

    def first(options):
        calls.append(tuple(options))
        return options[0]

    animator = CaptionAnimator(word_seconds=1.2, chooser=first)
    animator.activate(RuntimeScene.ALONE_IDLE)
    first_caption = animator.caption

    assert animator.visible_words == 1
    assert animator.visible_text == first_caption.split()[0]
    assert animator.pending_display is True
    # Reads, face frames, and snapshot reconciliation do not choose again.
    assert animator.caption == first_caption
    assert len(calls) == 1

    animator.activate(RuntimeScene.PEER_SEEN)
    animator.activate(RuntimeScene.ALONE_IDLE)
    assert len(calls) == 3
    assert first_caption not in calls[-1]
    assert animator.caption != first_caption


def test_given_caption_words_then_timing_advances_only_after_display_success():
    """Given a prefix, when display fails or time is early, then it cannot skip."""

    animator = CaptionAnimator(
        word_seconds=1.2,
        chooser=lambda options: "nothing moved. i checked.",
    )
    animator.activate(RuntimeScene.ALONE_IDLE)

    # The first word remains retryable until a successful display commit.
    assert animator.advance_if_due(100.0) is False
    assert animator.visible_text == "nothing"
    animator.mark_presented(10.0)
    assert animator.next_word_at == pytest.approx(11.2)
    assert animator.advance_if_due(11.199) is False
    assert animator.advance_if_due(11.2) is True
    assert animator.visible_text == "nothing moved."
    assert animator.advance_if_due(99.0) is False

    animator.mark_presented(11.2)
    assert animator.next_word_at == pytest.approx(12.4)

    seeded = CaptionAnimator(
        word_seconds=1.2,
        chooser=lambda options: "nothing moved. i checked.",
    )
    seeded.activate(RuntimeScene.ALONE_IDLE)
    seeded.mark_presented(20.0, transfer_seconds=2.3)
    # A slow full seed still leaves the first word visibly settled before the
    # next partial update, rather than immediately chasing the overdue timer.
    assert seeded.next_word_at == pytest.approx(20.6)


def test_given_invalid_caption_configuration_then_it_fails_explicitly():
    with pytest.raises(ValueError, match="Caption word timing"):
        RuntimePolicy(caption_word_seconds=0)
    with pytest.raises(ValueError, match="Caption word timing"):
        CaptionAnimator(word_seconds=0)

    animator = CaptionAnimator(chooser=lambda options: "not approved")
    with pytest.raises(ValueError, match="unavailable option"):
        animator.activate(RuntimeScene.ALONE_IDLE)
    valid = CaptionAnimator(chooser=lambda options: options[0])
    valid.activate(RuntimeScene.ALONE_IDLE)
    with pytest.raises(ValueError, match="transfer timing"):
        valid.mark_presented(0, transfer_seconds=-1)


def test_given_candidate_encounter_then_wink_plays_once_and_final_blush_holds():
    """Given a candidate, when frames complete, then wink cannot loop."""

    animator = SceneAnimator(RuntimePolicy(), reaction_random=lambda: 0.99)
    snapshot = _snapshot(PeerSnapshot("candidate", 1, probe_verdict="candidate"))
    animator.activate(RuntimeScene.CANDIDATE, snapshot)

    rendered = []
    while animator.has_next_frame:
        step = animator.current_step()
        rendered.append(step.expression)
        animator.mark_presented(step)

    assert tuple(rendered) == EXPECTED_SEQUENCES[RuntimeScene.CANDIDATE]
    assert animator.held is True
    assert animator.current_step().expression == "(˵•‿•˵)"
    assert animator.has_next_frame is False


def test_given_candidate_replacement_then_animation_identity_restarts():
    """Given another encounter, when reconciled, then its bashful sequence is new."""

    first = ProjectionEngine(RuntimePolicy(coalesce_seconds=0)).select(
        _snapshot(PeerSnapshot("candidate", 1, probe_verdict="candidate"))
    )
    second = ProjectionEngine(RuntimePolicy(coalesce_seconds=0)).select(
        _snapshot(PeerSnapshot("candidate", 2, probe_verdict="candidate"))
    )

    assert RuntimeController._animation_key(first) != RuntimeController._animation_key(
        second
    )


@pytest.mark.parametrize(
    "roll,expected,dwell",
    ((0.10, "(-‿-)⚡", 2.0), (0.25, "(◑‿◑)⚡", 4.0)),
)
def test_given_charging_center_then_seeded_reaction_is_bounded(roll, expected, dwell):
    """Given injected chance, when center succeeds, then one reaction is proofable."""

    animator = SceneAnimator(RuntimePolicy(), reaction_random=lambda: roll)
    animator.activate(RuntimeScene.CHARGING, _snapshot(battery=75, plugged=True))
    center = animator.current_step()
    animator.mark_presented(center)
    reaction = animator.current_step()

    assert center.expression == "(•‿•)⚡"
    assert reaction.expression == expected
    assert reaction.dwell_seconds == dwell
    assert reaction.kind == "reaction"

    animator.mark_presented(reaction)
    following = animator.current_step()
    assert following.kind == "base"
    assert following.expression == "(•ᴗ•)⚡"


def test_given_charging_center_then_no_reaction_roll_continues_base_loop():
    """Given the remaining probability, when selected, then no insert appears."""

    animator = SceneAnimator(RuntimePolicy(), reaction_random=lambda: 0.90)
    animator.activate(RuntimeScene.CHARGING, _snapshot(battery=75, plugged=True))
    animator.mark_presented(animator.current_step())

    assert animator.current_step().expression == "(•ᴗ•)⚡"
    assert animator.current_step().kind == "base"


def test_given_full_charge_edge_then_star_retries_and_commits_once():
    """Given 100%, when display succeeds, then the one-shot latches per edge."""

    animator = SceneAnimator(RuntimePolicy(), reaction_random=lambda: 0.99)
    below = _snapshot(battery=99, plugged=True)
    full = _snapshot(battery=100, plugged=True)
    animator.activate(RuntimeScene.CHARGING, below)

    assert animator.observe(full) is True
    first_attempt = animator.current_step()
    assert first_attempt.expression == "(★‿★)⚡"
    assert first_attempt.kind == "full_charge"
    # No mark means a failed display retries the exact one-shot.
    assert animator.current_step() == first_attempt

    animator.mark_presented(first_attempt)
    assert animator.observe(full) is False
    assert animator.current_step().expression == "(•‿•)⚡"

    assert animator.observe(below) is False
    assert animator.observe(full) is True
    assert animator.current_step().kind == "full_charge"


def test_given_invalid_charging_randomizer_then_failure_is_explicit():
    """Given a broken chooser, when center commits, then it fails closed."""

    animator = SceneAnimator(RuntimePolicy(), reaction_random=lambda: 1.0)
    animator.activate(RuntimeScene.CHARGING, _snapshot(battery=75, plugged=True))

    with pytest.raises(ValueError, match="0 <= value < 1"):
        animator.mark_presented(animator.current_step())


def test_given_a_closed_animation_loop_when_advanced_then_no_frame_repeats():
    """Given first equals last, when looping, then the next distinct frame wins."""

    sequence = SCENE_SEQUENCES[RuntimeScene.ALONE_IDLE]
    assert sequence[0] == sequence[-1]
    assert RuntimeController._advance_index(sequence, len(sequence) - 1) == 1


def test_given_runtime_run_when_boot_hands_off_then_full_seeds_partial_animation():
    """Given runtime handoff, when frames advance, then refresh modes are safe."""

    class SingleSnapshotSource:
        async def updates(self):
            yield SourceUpdate(_snapshot())
            await asyncio.Event().wait()

    async def scenario():
        stop = asyncio.Event()
        display = FakeDeviceManager()
        original_show = display.show

        async def show(image, refresh_mode="full"):
            await original_show(image, refresh_mode)
            if len(display.images) == 2:
                stop.set()

        display.show = show
        policy = RuntimePolicy(coalesce_seconds=0).with_frame_rates(
            ("alone_idle=0.001",)
        )
        controller = RuntimeController(display, FrameRenderer(), policy)
        await asyncio.wait_for(controller.run(SingleSnapshotSource(), stop), timeout=1)
        return display

    display = asyncio.run(scenario())

    assert len(display.images) == 2
    assert display.refresh_modes == ["full", "partial"]


def test_given_caption_deadlines_then_words_reveal_without_advancing_the_face():
    """Given a slow face, when words arrive, then only caption ink changes."""

    async def scenario():
        stop = asyncio.Event()

        class SingleSnapshotSource:
            async def updates(self):
                yield SourceUpdate(_snapshot())
                await asyncio.Event().wait()

        display = FakeDeviceManager()
        original_show = display.show

        async def show(image, refresh_mode="full"):
            await original_show(image, refresh_mode)
            if len(display.images) == 3:
                stop.set()

        display.show = show
        choices = []

        def choose(options):
            choices.append(tuple(options))
            return options[0]

        policy = RuntimePolicy(
            coalesce_seconds=0,
            caption_word_seconds=0.005,
        ).with_frame_rates(("alone_idle=30",))
        controller = RuntimeController(
            display,
            FrameRenderer(),
            policy,
            caption_choice=choose,
        )
        await asyncio.wait_for(controller.run(SingleSnapshotSource(), stop), timeout=1)
        return display, choices

    display, choices = asyncio.run(scenario())
    renderer = FrameRenderer()
    caption_bounds = renderer._caption_bounds(renderer.height - 20)
    faces = [
        image.crop((0, 21, image.width, caption_bounds[1])).tobytes()
        for image in display.images
    ]
    captions = [image.crop(caption_bounds).tobytes() for image in display.images]

    assert len(set(faces)) == 1
    assert len(set(captions)) == 3
    assert display.refresh_modes == ["full", "partial", "partial"]
    assert len(choices) == 1


def test_given_face_and_snapshot_updates_then_the_caption_clock_does_not_reset():
    """Given repeated authority, when faces move, then the first prefix holds."""

    async def scenario():
        stop = asyncio.Event()
        first_draw = asyncio.Event()

        class RepeatedSnapshotSource:
            async def updates(self):
                snapshot = _snapshot()
                yield SourceUpdate(snapshot)
                await first_draw.wait()
                yield SourceUpdate(snapshot, notification={"type": "wake"})
                await asyncio.Event().wait()

        display = FakeDeviceManager()
        original_show = display.show

        async def show(image, refresh_mode="full"):
            await original_show(image, refresh_mode)
            if len(display.images) == 1:
                first_draw.set()
            elif len(display.images) == 3:
                stop.set()

        display.show = show
        choices = []

        def choose(options):
            choices.append(tuple(options))
            return options[0]

        policy = RuntimePolicy(
            coalesce_seconds=0,
            caption_word_seconds=30,
        ).with_frame_rates(("alone_idle=0.005",))
        controller = RuntimeController(
            display,
            FrameRenderer(),
            policy,
            caption_choice=choose,
        )
        await asyncio.wait_for(
            controller.run(RepeatedSnapshotSource(), stop), timeout=1
        )
        return display, choices

    display, choices = asyncio.run(scenario())
    renderer = FrameRenderer()
    caption_bounds = renderer._caption_bounds(renderer.height - 20)
    captions = [image.crop(caption_bounds).tobytes() for image in display.images]

    assert len(set(captions)) == 1
    assert len(choices) == 1
    assert display.refresh_modes == ["full", "partial", "partial"]


def test_given_higher_priority_state_then_current_animation_is_interrupted_now():
    """Given candidate motion, when sync starts, then no candidate timer blocks it."""

    async def scenario():
        stop = asyncio.Event()
        candidate_drawn = asyncio.Event()

        class StateSource:
            async def updates(self):
                candidate = PeerSnapshot("peer", 1, probe_verdict="candidate")
                yield SourceUpdate(_snapshot(candidate))
                await candidate_drawn.wait()
                syncing = PeerSnapshot("peer", 1, sync_state="running")
                yield SourceUpdate(_snapshot(syncing))
                await asyncio.Event().wait()

        display = FakeDeviceManager()
        original_show = display.show

        async def show(image, refresh_mode="full"):
            await original_show(image, refresh_mode)
            if len(display.images) == 1:
                candidate_drawn.set()
            elif len(display.images) == 2:
                stop.set()

        display.show = show
        policy = RuntimePolicy(coalesce_seconds=0).with_frame_rates(
            ("candidate=30", "sync_running=30")
        )
        controller = RuntimeController(
            display,
            FrameRenderer(),
            policy,
            reaction_random=lambda: 0.99,
            caption_choice=lambda options: options[0],
        )
        await asyncio.wait_for(controller.run(StateSource(), stop), timeout=1)
        return display

    display = asyncio.run(scenario())
    renderer = FrameRenderer()
    candidate = renderer.render_runtime(
        RuntimeFrame(
            RuntimeScene.CANDIDATE,
            EXPECTED_SEQUENCES[RuntimeScene.CANDIDATE][0],
            0,
            _snapshot(PeerSnapshot("peer", 1, probe_verdict="candidate")),
            SCENE_CAPTIONS[RuntimeScene.CANDIDATE][0],
            1,
        )
    )
    syncing = renderer.render_runtime(
        RuntimeFrame(
            RuntimeScene.SYNC_RUNNING,
            EXPECTED_SEQUENCES[RuntimeScene.SYNC_RUNNING][0],
            0,
            _snapshot(PeerSnapshot("peer", 1, sync_state="running")),
            SCENE_CAPTIONS[RuntimeScene.SYNC_RUNNING][0],
            1,
        )
    )

    assert display.images[0].tobytes() == candidate.tobytes()
    assert display.images[1].tobytes() == syncing.tobytes()
    assert display.refresh_modes == ["full", "partial"]


def test_given_legacy_boot_when_rendered_then_only_its_first_frame_is_full():
    """Given legacy boot, when it advances, then content stays and resets do not."""

    class Notifier:
        def ready(self, status="Boot splash rendered"):
            return True

    display = FakeDeviceManager()
    controller = ScreenController(display, FrameRenderer())
    asyncio.run(
        controller.boot(
            SyntheticReadinessMonitor(),
            Notifier(),
            poll_interval=0,
            settle_seconds=0,
        )
    )

    assert len(display.images) == 3 + len(SERVICE_SPECS)
    assert display.refresh_modes == ["full"] + ["partial"] * (len(display.images) - 1)


def test_given_persistent_fact_clears_then_controller_wakes_without_another_push():
    """Given candidate clears, when the stream is quiet, then idle follows dwell."""

    async def scenario():
        stop = asyncio.Event()
        first_draw = asyncio.Event()

        class TwoSnapshotSource:
            async def updates(self):
                candidate = PeerSnapshot("peer", 1, probe_verdict="candidate")
                yield SourceUpdate(_snapshot(candidate))
                await first_draw.wait()
                yield SourceUpdate(_snapshot())
                await asyncio.Event().wait()

        display = FakeDeviceManager()
        original_show = display.show

        async def show(image, refresh_mode="full"):
            await original_show(image, refresh_mode)
            if len(display.images) == 1:
                first_draw.set()
            elif len(display.images) == 2:
                stop.set()

        display.show = show
        policy = RuntimePolicy(coalesce_seconds=0).with_minimum_dwells(
            ("candidate=0.01",)
        )
        controller = RuntimeController(display, FrameRenderer(), policy)
        await asyncio.wait_for(controller.run(TwoSnapshotSource(), stop), timeout=1)
        return display

    display = asyncio.run(scenario())
    assert display.refresh_modes == ["full", "partial"]


def test_given_display_failure_then_transient_retries_before_being_consumed():
    """Given a failed submission, when display recovers, then payoff is delivered."""

    async def scenario():
        stop = asyncio.Event()
        first_draw = asyncio.Event()

        class RecognitionSource:
            async def updates(self):
                yield SourceUpdate(_snapshot())
                await first_draw.wait()
                peer = PeerSnapshot("peer", 1, recognized=True, known_before=False)
                yield SourceUpdate(_snapshot(peer))
                await asyncio.Event().wait()

        class FlakyDisplay(FakeDeviceManager):
            def __init__(self):
                super().__init__()
                self.attempted_modes = []

            async def show(self, image, refresh_mode="full"):
                self.attempted_modes.append(refresh_mode)
                if len(self.attempted_modes) == 2:
                    raise RuntimeError("temporary display outage")
                await super().show(image, refresh_mode)
                if len(self.attempted_modes) == 1:
                    first_draw.set()
                elif len(self.attempted_modes) == 3:
                    stop.set()

        display = FlakyDisplay()
        policy = RuntimePolicy(coalesce_seconds=0, reconnect_seconds=0)
        controller = RuntimeController(display, FrameRenderer(), policy)
        await asyncio.wait_for(controller.run(RecognitionSource(), stop), timeout=1)
        return display, controller

    display, controller = asyncio.run(scenario())

    assert display.attempted_modes == ["full", "partial", "partial"]
    assert len(display.images) == 2
    assert not controller.projector._pending


def test_given_runtime_draw_when_submitted_then_partial_mode_crosses_api_boundary():
    """Given an animation frame, when posted, then partial is explicit."""

    class CapturingDisplay(DeviceManagerDisplay):
        def __init__(self):
            self.requests = []

        def _request(self, path, *, payload=None, timeout=5.0):
            self.requests.append((path, payload, timeout))
            return {"success": True}

    display = CapturingDisplay()
    asyncio.run(display.show(Image.new("1", (2, 2), 255), refresh_mode="partial"))

    path, payload, timeout = display.requests[0]
    assert path == "/display/image"
    assert payload["refresh_mode"] == "partial"
    assert payload["image_base64"]
    assert timeout == 45.0


def test_given_replay_command_when_run_then_refreshes_are_seeded_and_exported(
    tmp_path,
):
    """Given replay, when run, then full seeds partial frames and atlas emits."""

    display = FakeDeviceManager()
    renderer = FrameRenderer()
    controller = RuntimeController(display, renderer)
    atlas = tmp_path / "screen-atlas.png"

    asyncio.run(
        controller.replay_all_states(
            synthetic_snapshot("metot"),
            frame_seconds=0,
            atlas_output=str(atlas),
        )
    )

    expected_count = sum(len(replay_sequence(scene)) for scene in RuntimeScene)
    assert display.waited
    assert len(display.images) == expected_count
    assert display.refresh_modes == ["full"] + ["partial"] * (expected_count - 1)
    assert atlas.is_file()
    with Image.open(str(atlas)) as image:
        expected_rows = (expected_count + 3) // 4
        assert image.size == (renderer.width * 4, renderer.height * expected_rows)


def test_given_caption_proof_when_rendered_then_every_phrase_and_prefix_exists(
    tmp_path,
):
    """Given deterministic proof, when exported, then all copy is inspectable."""

    display = FakeDeviceManager()
    renderer = FrameRenderer()
    controller = RuntimeController(display, renderer)
    snapshot = synthetic_snapshot("metot")
    frames = controller.caption_proof_frames(snapshot)
    assert len(frames) == 253

    complete = {
        (frame.scene, frame.caption)
        for frame in frames
        if frame.caption_word_count == len(frame.caption.split())
    }
    assert complete.issuperset(
        {
            (scene, caption)
            for scene in RuntimeScene
            for caption in SCENE_CAPTIONS[scene]
        }
    )
    for scene in RuntimeScene:
        representative = max(
            SCENE_CAPTIONS[scene],
            key=lambda caption: (len(caption.split()), len(caption)),
        )
        assert {
            frame.caption_word_count
            for frame in frames
            if frame.scene == scene and frame.caption == representative
        }.issuperset(range(1, len(representative.split()) + 1))
        for index, expression in enumerate(replay_sequence(scene)):
            assert any(
                frame.scene == scene
                and frame.expression == expression
                and frame.sequence_index == index
                for frame in frames
            )

    atlas = tmp_path / "caption-proof.png"
    controller.render_caption_proof(snapshot, atlas_output=str(atlas))
    assert display.images == []
    assert atlas.is_file()
    with Image.open(str(atlas)) as image:
        assert image.mode == "1"
        expected_rows = (len(frames) + 3) // 4
        assert image.size == (renderer.width * 4, renderer.height * expected_rows)


def test_given_caption_proof_without_output_then_failure_is_explicit():
    controller = RuntimeController(FakeDeviceManager(), FrameRenderer())
    with pytest.raises(ValueError, match="requires --atlas-output"):
        controller.render_caption_proof(synthetic_snapshot(), atlas_output="")


def test_given_cli_when_parsed_then_both_replay_spellings_are_available():
    """Given operators, when invoking replay, then the proof command exists."""

    assert _parser().parse_args(["replay-states"]).command == "replay-states"
    assert _parser().parse_args(["replay-all-states"]).command == ("replay-all-states")
    proof = _parser().parse_args(["proof-captions"])
    assert proof.command == "proof-captions"
    assert proof.caption_word_seconds == 1.2


FEATURE_PATH = Path(__file__).parents[1] / "features" / "totem_screen.feature"


def _feature_scenario_names():
    text = FEATURE_PATH.read_text(encoding="utf-8")
    return tuple(
        match.group(1).strip()
        for match in re.finditer(
            r"^\s*Scenario(?: Outline)?:\s*(.+?)\s*$", text, flags=re.MULTILINE
        )
    )


def _bind_exact_catalog():
    test_given_the_product_catalog_when_loaded_then_only_exact_sequences_exist()
    for scene in RuntimeScene:
        sequence = replay_sequence(scene)
        for index, expression in enumerate(sequence):
            test_given_each_exact_frame_when_rendered_then_vector_ink_is_visible(
                scene, index, expression
            )
    example_rows = set(
        re.findall(
            r"^\s*\|\s*([a-z][a-z_]*)\s*\|\s*$",
            FEATURE_PATH.read_text(encoding="utf-8"),
            flags=re.MULTILINE,
        )
    )
    example_rows.discard("scene")
    assert example_rows == {scene.value for scene in RuntimeScene}


def _bind_priority():
    test_given_competing_axes_when_projected_then_priority_is_deterministic()
    test_given_higher_priority_activity_then_ambient_dwell_does_not_block_it()


def _bind_reconnect():
    test_given_failed_sse_connect_when_retried_then_reconnect_snapshot_arrives()
    test_given_connected_sse_reaches_eof_then_a_new_stream_reconciles_first()


def _bind_header_footer():
    test_given_runtime_facts_when_rendered_then_layout_contract_is_stable()
    test_given_status_row_mismatch_then_footer_counts_use_the_same_live_peer_rows()


def _bind_replay():
    with tempfile.TemporaryDirectory(prefix="totem-screen-bdd-", dir="/tmp") as root:
        test_given_replay_command_when_run_then_refreshes_are_seeded_and_exported(
            Path(root)
        )
    test_given_cli_when_parsed_then_both_replay_spellings_are_available()


def _bind_captions():
    test_given_caption_catalog_when_loaded_then_every_exact_option_is_present()
    test_given_caption_admissions_then_selection_is_stable_and_non_repeating()
    test_given_caption_words_then_timing_advances_only_after_display_success()
    test_given_all_captions_and_prefixes_when_rendered_then_the_band_is_safe()


def _bind_caption_proof():
    with tempfile.TemporaryDirectory(prefix="totem-caption-bdd-", dir="/tmp") as root:
        test_given_caption_proof_when_rendered_then_every_phrase_and_prefix_exists(
            Path(root)
        )


# Lightweight scenario bindings keep the checked-in feature executable without
# adding a second test framework.  Each binding invokes the same deterministic
# contract exercised as a first-class pytest test above.
FEATURE_BINDINGS = {
    "Every permitted runtime scene renders its exact sequence": _bind_exact_catalog,
    "Orthogonal facts are arbitrated by priority": _bind_priority,
    "SSE is a notification and never state authority": (
        test_given_sse_notification_when_received_then_fresh_snapshot_is_authority
    ),
    "A quiet event stream still refreshes persistent facts": (
        test_given_silent_sse_when_poll_elapses_then_snapshot_is_refreshed
    ),
    "A lost event stream reconnects safely": _bind_reconnect,
    "Fast encounter progress is coalesced": (
        test_given_burst_updates_when_arbitrated_then_the_latest_snapshot_is_coalesced
    ),
    "Social payoff has a minimum dwell": (
        test_given_social_payoff_when_lower_priority_arrives_then_minimum_dwell_holds
    ),
    "Process restart does not replay stale payoffs": (
        test_given_startup_snapshot_when_seeded_then_stale_payoffs_are_not_replayed
    ),
    "Ambient copy distinguishes company from loneliness": (
        test_given_online_friend_after_payoffs_then_neutral_idle_replaces_lonely_idle
    ),
    "A departed sync is reconciled without reviving its peer": (
        test_given_departed_tombstone_then_only_cancelled_payoff_is_projected
    ),
    "Header and footer communicate persistent facts": _bind_header_footer,
    "Every state can be proofed on hardware": _bind_replay,
    "Captions belong to authoritative scene admissions": _bind_captions,
    "Every caption can be proofed without a long hardware replay": (
        _bind_caption_proof
    ),
    "Boot retains its lifecycle without avoidable full resets": (
        test_given_legacy_boot_when_rendered_then_only_its_first_frame_is_full
    ),
}


def test_every_checked_in_gherkin_scenario_has_one_executable_binding():
    """Given the feature, when collected, then no scenario is documentary-only."""

    scenario_names = _feature_scenario_names()
    assert len(scenario_names) == len(set(scenario_names))
    assert set(scenario_names) == set(FEATURE_BINDINGS)
    assert all(callable(binding) for binding in FEATURE_BINDINGS.values())


@pytest.mark.parametrize("scenario_name", _feature_scenario_names())
def test_given_checked_in_gherkin_scenario_when_run_then_binding_passes(
    scenario_name,
):
    """Given each Gherkin scenario, when run, then its live contract passes."""

    FEATURE_BINDINGS[scenario_name]()
