#!/usr/bin/env python3
"""Join the docking recordings into one comparison video.

The recordings live next to this script, one pair per speed:

    <speed> - Landing.mp4              the ship arrives the normal way
    <speed> - Upside Down Landing.mp4  the ship arrives at an odd attitude

The output holds every pair, slowest speed first and the upright clip before
the upside down one in each pair. Each segment is labelled with its speed and
its case, and carries a timer that runs from the frame the game takes the
ship over to the frame the ship is down.

Both ends of the timer are found automatically.

The start is the frame the game prints "Initiating landing sequence" across
the screen, which is when the docking procedure begins. The message is white
text on a dark background, so the band that carries it is scanned for the
number of bright runs: glyphs make hundreds of runs, a lit wall makes a few.
The message fades in, so the timer starts once the text has faded halfway
in, which is the same point in every recording.

The end is the cut to black that the game plays once the ship is down and
the pilot is put out.

The video is re-encoded losslessly, so the result is bit identical to the
recordings apart from the overlay. The audio is re-encoded, because the
segments have to be joined and the sources are AAC.

Usage:
    python3 assets/combine.py            # lossless master
    python3 assets/combine.py --web      # browser friendly instead
"""

import argparse
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
FONT = os.path.join(HERE, "fonts", "GeosansLight-NMS.ttf")
OUT_DIR = os.path.join(HERE, "video")

# The pairs, slowest speed first, upright before upside down.
SPEEDS = ["2x", "5x", "10x"]
CASES = [("Landing", "LANDING"), ("Upside Down Landing", "UPSIDE DOWN LANDING")]

FPS = 60
WIDTH, HEIGHT = 2560, 1440

# The band of the screen that carries the "Initiating landing sequence"
# message, and how the message is told apart from the scene behind it.
TEXT_X, TEXT_Y, TEXT_W, TEXT_H = 1090, 381, 378, 18
TEXT_LEVEL = 200  # the text is white, the station is not that bright
TEXT_FADE = 0.5  # the timer starts when the text has faded this far in
TEXT_HOLD = 30  # frames the message has to stay up to count as shown

# The screen is black once the landing has ended and the pilot is put out.
DARK_LEVEL = 2.0
DARK_HOLD = 3

# Overlay layout.
SPEED_X, SPEED_Y, SPEED_SIZE = 60, 44, 72
CASE_X, CASE_Y, CASE_SIZE = 64, 140, 30
TIMER_X, TIMER_Y, TIMER_SIZE = 64, 190, 52
TIMER_W = 119  # the width of "00.00" at the timer size
UNIT_SIZE = 32
AMBER = "0xFFC878"
WHITE = "0xFFFFFF"
GREY = "0x9AA0A6"
EDGE = "borderw=2:bordercolor=0x000000@0.8"


def run(cmd):
    """Run a command, raising with its output on failure."""
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise SystemExit("%s failed:\n%s" % (" ".join(cmd[:3]), proc.stderr[-4000:]))
    return proc.stdout


def frame_count(clip):
    """Return the number of frames a recording holds."""
    out = run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-count_frames",
               "-show_entries", "stream=nb_read_frames", "-of", "csv=p=0", clip])
    return int(out.strip().split(",")[0])


def decode(clip, vf, width, height):
    """Decode a clip to raw greyscale frames of the given size.

    Every frame the file holds is passed through, so the frame numbers here
    are the frame numbers of the recording.
    """
    cmd = ["ffmpeg", "-v", "error", "-i", clip, "-vf", vf,
           "-fps_mode", "passthrough", "-f", "rawvideo", "-pix_fmt", "gray", "-"]
    proc = subprocess.run(cmd, capture_output=True)
    if proc.returncode != 0:
        raise SystemExit("ffmpeg failed on %s:\n%s" % (clip, proc.stderr[-2000:]))
    data = proc.stdout
    frame = width * height
    return [data[i * frame:(i + 1) * frame] for i in range(len(data) // frame)]


def text_runs(frame):
    """Count the bright runs in a band of the message.

    A line of glyphs breaks into many runs, a lit wall into a few.
    """
    runs = 0
    for y in range(TEXT_H):
        row = frame[y * TEXT_W:(y + 1) * TEXT_W]
        previous = False
        for value in row:
            bright = value > TEXT_LEVEL
            if bright and not previous:
                runs += 1
            previous = bright
    return runs


def find_takeover(clip):
    """Return the frame the game takes the ship over on, or None."""
    frames = decode(clip, "crop=%d:%d:%d:%d" % (TEXT_W, TEXT_H, TEXT_X, TEXT_Y),
                    TEXT_W, TEXT_H)
    counts = [text_runs(f) for f in frames]
    if not counts:
        return None

    # The message sits at full strength for most of the clip, so the top of
    # the counts is the text and half of it is the text half faded in.
    top = sorted(counts, reverse=True)[:max(1, len(counts) // 5)]
    threshold = sorted(top)[len(top) // 2] * TEXT_FADE

    for i in range(len(counts) - TEXT_HOLD):
        if all(c >= threshold for c in counts[i:i + TEXT_HOLD]):
            return i
    return None


def find_down(clip):
    """Return the frame the ship is down on, or None."""
    width, height = 320, 180
    frames = decode(clip, "scale=%d:%d" % (width, height), width, height)
    levels = [sum(f) / float(len(f)) for f in frames]
    for i in range(len(levels) - DARK_HOLD):
        if all(v < DARK_LEVEL for v in levels[i:i + DARK_HOLD]):
            return i
    return None


def timer_text(start, end):
    """The drawtext text that shows the elapsed time as SS.hh."""
    span = end - start
    elapsed = "(min(max(t-%.6f,0),%.6f))" % (start, span)
    hundredths = "(floor(%s*100+0.5))" % elapsed
    return (
        "%{eif\\:floor(" + hundredths + "/1000)\\:d}"
        "%{eif\\:mod(floor(" + hundredths + "/100)\\,10)\\:d}."
        "%{eif\\:floor(mod(" + hundredths + "\\,100)/10)\\:d}"
        "%{eif\\:mod(" + hundredths + "\\,10)\\:d}"
    )


def draw(text, x, y, size, colour, enable=None):
    """A drawtext that draws the given text in the game's font."""
    opts = ["fontfile=%s" % FONT, "text='%s'" % text,
            "x=%s" % x, "y=%d" % y, "fontsize=%d" % size,
            "fontcolor=%s" % colour, EDGE]
    if enable:
        opts.append("enable='%s'" % enable)
    return "drawtext=" + ":".join(opts)


def build_graph(segments):
    """Build the filter graph for the segments."""
    lines = []
    for index, segment in enumerate(segments):
        start = segment["start"]
        end = segment["end"]
        # The timer only runs once the game has taken the ship over.
        after = "gte(t,%.6f)" % start

        text = [
            draw(segment["speed"], SPEED_X, SPEED_Y, SPEED_SIZE, AMBER),
            draw(segment["label"], CASE_X, CASE_Y, CASE_SIZE, WHITE),
            draw(timer_text(start, end), TIMER_X, TIMER_Y, TIMER_SIZE, WHITE, after),
            draw("s", TIMER_X + TIMER_W + 12, TIMER_Y + 16, UNIT_SIZE, GREY, after),
        ]
        parts = text
        # The frames are put back on a plain 60 fps timeline so that the
        # timer counts seconds and not the jitter of the recording.
        lines.append("[%d:v]setpts=N/(%d*TB),scale=%d:%d,setsar=1,%s[v%d];"
                     % (index, FPS, WIDTH, HEIGHT, ",".join(parts), index))
        lines.append("[%d:a]aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo,"
                     "apad,atrim=end=%.6f,asetpts=N/SR/TB[a%d];"
                     % (index, segment["frames"] / float(FPS), index))
    chains = "".join("[v%d][a%d]" % (i, i) for i in range(len(segments)))
    lines.append("%sconcat=n=%d:v=1:a=1[outv][outa]" % (chains, len(segments)))
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--web", action="store_true",
                        help="encode for the web instead of losslessly")
    parser.add_argument("--out", default=None)
    args = parser.parse_args()

    if args.out is None:
        name = "landing-comparison-web.mp4" if args.web else "landing-comparison-lossless.mp4"
        args.out = os.path.join(OUT_DIR, name)

    segments = []
    for speed in SPEEDS:
        for case, label in CASES:
            clip = os.path.join(HERE, "%s - %s.mp4" % (speed, case))
            if not os.path.isfile(clip):
                raise SystemExit("missing recording: %s" % clip)
            takeover = find_takeover(clip)
            down = find_down(clip)
            if takeover is None or down is None:
                raise SystemExit("could not find the landing sequence in %s" % clip)
            frames = frame_count(clip)
            segments.append({
                "clip": clip,
                "label": label,
                "speed": speed,
                "frames": frames,
                "start": takeover / float(FPS),
                "end": down / float(FPS),
            })
            print("%-34s takeover %4.2f s, down %4.2f s, landing %4.2f s"
                  % (os.path.basename(clip), takeover / float(FPS),
                     down / float(FPS), (down - takeover) / float(FPS)))

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    graph = os.path.join(OUT_DIR, "filtergraph.txt")
    with open(graph, "w", encoding="utf-8") as handle:
        handle.write(build_graph(segments))

    cmd = ["ffmpeg", "-y", "-v", "error", "-vsync", "0"]
    for segment in segments:
        cmd += ["-i", segment["clip"]]
    cmd += ["-filter_complex_script", graph, "-map", "[outv]", "-map", "[outa]"]
    if args.web:
        cmd += ["-c:v", "libx264", "-crf", "18", "-preset", "slow", "-pix_fmt", "yuv420p"]
    else:
        cmd += ["-c:v", "libx264", "-qp", "0", "-preset", "medium", "-pix_fmt", "yuv420p"]
    cmd += ["-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", args.out]
    run(cmd)

    size = os.path.getsize(args.out)
    print("wrote %s (%.1f MB, %s)" % (args.out, size / 1048576.0,
                                       "web" if args.web else "lossless"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
