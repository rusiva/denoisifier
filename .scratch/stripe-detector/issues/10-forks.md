# 10: Forks

**What to build:** The report shows where stripes split or end. The generator gains forks: points with direction ±1, where the phase winds by 2π around the point. `analyse` finds forks from the local phase and reports each one as a point with a direction (splitting upward or downward).

**Blocked by:** 05

**Status:** ready-for-agent

- [ ] The generator places forks with either direction, and returns their true points and directions.
- [ ] Forks are found at typical noise with the correct direction, within one period of the true point.
- [ ] A fork near a phase break is still found and kept separate from the break. (If 09 isn't done yet, generate the break in the test anyway; only the fork is checked.)
- [ ] A frame with forks is still recognised as striped.
- [ ] The report lists `forks`, each with a point and a direction.
