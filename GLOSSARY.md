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

**Clipped Pixel**:
A pixel at or above the clip level, whose true value the frame does not show.
_Avoid_: overexposed

### Stripe structure

**Period**:
The spacing between neighbouring stripes, in sensor pixels, measured across the stripes.
_Avoid_: wavelength, pitch, spacing

**Angle**:
The tilt of the stripes from vertical, in degrees. Row 0 of the frame is the top. Positive means the top of each stripe leans right (moving down the frame, a stripe shifts left).
_Avoid_: orientation, rotation, tilt angle

**Striped Region**:
The part of a frame where stripes are present. It may cover only part of the envelope.
_Avoid_: stripe area, patch

**Mask**:
An array the shape of the Frame that labels each pixel with the Striped Region it belongs to: 0 for none, k for region k of the report. The boolean mask is the union of the regions (label > 0).
_Avoid_: region image, segmentation

**Phase Break**:
A line across the stripes where every stripe on one side is shifted sideways relative to the other side. Period and angle stay the same on both sides.
_Avoid_: fault, discontinuity, glitch

**Fork**:
A point where one stripe splits into two, or where a stripe ends.
_Avoid_: dislocation, defect, branch

### The verdict

**Stripe-free**:
True of a frame that really contains no stripes (modulation depth 0 everywhere). A fact about the frame, not a call made by the detector.
_Avoid_: clean, not striped, negative

**Stripe Score**:
A continuous, unbounded measure of how strongly a frame shows stripes; higher means more stripe-like. It is not a probability.
_Avoid_: confidence, probability, likelihood, SNR

**Threshold**:
The stripe score above which the verdict is Striped, set so that about 1% of stripe-free frames are false alarms.
_Avoid_: cutoff, limit

**Verdict**:
The detector's yes/no call on a frame: **Striped** if it finds at least one striped region anywhere, however small, otherwise **Not Striped**.
_Avoid_: detection, result, classification

**False Alarm**:
A stripe-free frame whose verdict is Striped.
_Avoid_: false positive, misdetection
