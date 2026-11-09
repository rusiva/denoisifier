# Denoisifier

Finds the stripe-formation effect in noisy camera intensity data, and maps where the stripes are and where their periodic structure is broken.

## Language

### What a frame contains

**Frame**:
One 2D array of intensity values from one camera exposure.
_Avoid_: image, map, snapshot

**Profile**:
The smooth, distorted 2D Gaussian shape of the light spot.
_Avoid_: beam, Gaussian, signal

**Mottle**:
Random brightness variation with no repeating pattern, multiplying the profile. Its features can be as small as stripe spacing or much larger.
_Avoid_: texture, background noise

**Envelope**:
The profile multiplied by the mottle: what the frame would show with no stripes and no noise.
_Avoid_: background, baseline, signal

**Stripes**:
The physical effect being sought: a roughly periodic, near-vertical pattern that multiplies the envelope.
_Avoid_: fringes, pattern, signal

**Modulation Depth**:
How strongly the stripes raise and lower the envelope, from 0 (no stripes) to 1 (fully dark between stripes).
_Avoid_: contrast, amplitude, visibility

**Noise**:
Random intensity variation from pixel to pixel and from frame to frame, on top of everything else.
_Avoid_: grain

**Spike**:
A single bright pixel or short bright streak from a cosmic-ray hit or a hot pixel, unrelated to the scene.
_Avoid_: outlier, glitch, hot spot

### Stripe structure

**Striped Region**:
The part of a frame where stripes are present. It may cover only part of the envelope.
_Avoid_: stripe area, patch

**Phase Break**:
A line across the stripes where every stripe on one side is shifted sideways relative to the other side. Period and orientation stay the same on both sides.
_Avoid_: fault, discontinuity, glitch

**Fork**:
A point where one stripe splits into two, or where a stripe ends.
_Avoid_: dislocation, defect, branch
