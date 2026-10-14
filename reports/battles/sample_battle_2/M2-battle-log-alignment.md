# M2 Battle Log extraction and video alignment

The existing 360–400-second cache is sufficient to read and reconstruct **all 20 entries in the visible Turn 2 log**. All 20 agree with the corresponding sampled battle observations. This completes the manual extraction/alignment experiment; it does not establish automated OCR accuracy or whole-battle event coverage.

## Evidence and timing

Source: `tests/fixtures/sample_battle_2.mp4`. The working tree was clean at resumption; the existing survey manifest and frames were reused unchanged. No prior M2 report or implementation was present in the working tree.

At 266 seconds the video is in command selection, with Rillaboom and Archaludon facing Raichu and Armarouge (Armarouge displays 30% HP). The relevant action sequence begins around 281 seconds and finishes around 342 seconds. The log is closed/transitioning at the nominal 371-second sample, first fully readable at 372 seconds, and remains visible through 380 seconds. Its heading is **回合 2** (Turn 2); 266 seconds is a context anchor, not a verified exact turn boundary.

The existing survey contains 40 frames at 1 fps, nominal timestamps 360–399 seconds, scaled to width 1311. Its manifest explicitly gives ±1-second timestamp uncertainty and resampled grid times rather than original frame PTS. Six unobscured log views at 372–377 seconds cover the complete top-to-bottom list. The first viewport initially shows the bottom; scrolling upward exposes the start at 374 seconds, then scrolling downward repeats the middle and end. The countdown overlay at 378–380 obscures rows, but earlier views already contain them clearly. No additional log extraction was needed.

The missing battle evidence was extracted **once, only over [266, 360) seconds**, at 2 fps and the same width: 188 frames in `.cache/m2-alignment-266-360`, with command and nominal times in `frames.json`. Battle times below identify representative readable samples, with ±0.5-second sampling uncertainty; they are not exact action-onset times. Log-view times identify when historical entries were read, not when the events occurred. Preserve this distinction when consuming the [structured events](M2-battle-log-alignment.json).

## Ordered transcription and comparison

Chinese text is manually transcribed with line breaks collapsed. Side attribution comes from the text, row colors, and matching battle participants. English descriptions normalize the visible messages. Chronology comes from row order and overlapping viewports, independently corroborated by battle observations; sorting by log capture time would give the wrong order.

| Order | Visible log entry | Log view (s) | Battle sample (s) | Comparison |
| --- | --- | --- | --- | --- |
| 1 | 训练家换下了雷丘！ | [374](M2-battle-log-evidence/log-374.png) | [281](M2-battle-log-evidence/battle-281.jpg) | Opponent withdraws Raichu; consistent. |
| 2 | 训练家派出了爱管侍！ | [374](M2-battle-log-evidence/log-374.png) | [284](M2-battle-log-evidence/battle-284.jpg) | Opponent sends out Indeedee; consistent. |
| 3 | 爱管侍的精神制造者 | [374](M2-battle-log-evidence/log-374.png) | [288](M2-battle-log-evidence/battle-288.jpg) | Indeedee: Psychic Surge; consistent. |
| 4 | 脚下传来了奇妙的感觉！ | [374](M2-battle-log-evidence/log-374.png) | [289](M2-battle-log-evidence/battle-289.jpg) | Psychic Terrain begins; consistent. |
| 5 | 轰擂金刚猩，回来！ | [374](M2-battle-log-evidence/log-374.png) | [290](M2-battle-log-evidence/battle-290.jpg) | Player withdraws Rillaboom; consistent. |
| 6 | 上吧！蚊香蛙皇！ | [374](M2-battle-log-evidence/log-374.png) | [294](M2-battle-log-evidence/battle-294.jpg) | Player sends out Politoed; consistent. |
| 7 | 蚊香蛙皇的降雨 | [375](M2-battle-log-evidence/log-375.png) | [296.5](M2-battle-log-evidence/battle-296.5.jpg) | Politoed: Drizzle; consistent. |
| 8 | 开始下雨了！ | [375](M2-battle-log-evidence/log-375.png) | [297](M2-battle-log-evidence/battle-297.jpg) | Rain begins; consistent. |
| 9 | 对手的红莲铠骑使出了铠农炮！ | [376](M2-battle-log-evidence/log-376.png) | [298.5](M2-battle-log-evidence/battle-298.5.jpg) | Armarouge uses Armor Cannon on Politoed; consistent. |
| 10 | 蚊香蛙皇 HP 197 → 173 | [376](M2-battle-log-evidence/log-376.png) | [303](M2-battle-log-evidence/battle-303.jpg) | Politoed loses 24 HP; 197 → 173; consistent. |
| 11 | 对蚊香蛙皇效果不好。 | [377](M2-battle-log-evidence/log-377.png) | [304.5](M2-battle-log-evidence/battle-304.5.jpg) | Not very effective on Politoed; consistent. |
| 12 | 对手的红莲铠骑的防御、特防降低了！ | [377](M2-battle-log-evidence/log-377.png) | [306.5](M2-battle-log-evidence/battle-306.5.jpg) | Armarouge Defense and Special Defense fall; consistent. |
| 13 | 铝钢桥龙使出了电光束！ | [377](M2-battle-log-evidence/log-377.png) | [310](M2-battle-log-evidence/battle-310.jpg) | Archaludon uses Electro Shot; consistent. |
| 14 | 铝钢桥龙吸收了电力！ | [373](M2-battle-log-evidence/log-373.png) | [316](M2-battle-log-evidence/battle-316.jpg) | Archaludon absorbs electricity; consistent. |
| 15 | 铝钢桥龙的特攻提高了！ | [372](M2-battle-log-evidence/log-372.png) | [318.5](M2-battle-log-evidence/battle-318.5.jpg) | Archaludon Special Attack rises; consistent. |
| 16 | 红莲铠骑 HP 30% → 0% | [372](M2-battle-log-evidence/log-372.png) | [324](M2-battle-log-evidence/battle-324.jpg) | Armarouge displayed HP falls 30% → 0%; consistent. |
| 17 | 对手的红莲铠骑倒下了！ | [372](M2-battle-log-evidence/log-372.png) | [325.5](M2-battle-log-evidence/battle-325.5.jpg) | Armarouge faints; consistent. |
| 18 | 训练家派出了大狃拉！ | [372](M2-battle-log-evidence/log-372.png) | [335](M2-battle-log-evidence/battle-335.jpg) | Opponent sends out Sneasler; consistent. |
| 19 | 大狃拉的精神种子 | [372](M2-battle-log-evidence/log-372.png) | [338.5](M2-battle-log-evidence/battle-338.5.jpg) | Sneasler: Psychic Seed activates; consistent. |
| 20 | 对手的大狃拉的特防提高了！ | [372](M2-battle-log-evidence/log-372.png) | [342](M2-battle-log-evidence/battle-342.jpg) | Sneasler Special Defense rises; consistent. |

## Alignment findings and limits

The sequence is: opponent Raichu → Indeedee and Psychic Terrain; player Rillaboom → Politoed and rain; Armarouge's Armor Cannon hits Politoed; Archaludon's Electro Shot resolves against Armarouge; Armarouge faints; opponent Sneasler enters and activates Psychic Seed, followed by its Special Defense increase. The battle text and ability/item banners corroborate the corresponding log rows. The final command HUD shows Politoed 173/197, Archaludon 197/197, Indeedee 100%, and Sneasler 100% (also visible in the reused 371-second frame).

Politoed's log records 197 → 173, a loss of 24 HP. The reviewed 303-second video HUD independently confirms 173/197 after Armor Cannon. The exact pre-hit value here is transcribed from the log; this comparison does not claim two independent HUD endpoint readings. The resistance message appears at 304.5 seconds, and Armarouge's Defense/Special Defense decrease at 306.5 seconds.

Electro Shot's move announcement precedes the electricity-absorption message and Special Attack increase. The video shows the attack animation around 319–323 seconds and Armarouge's HP draining afterward. Its intermediate **14% at 323.5 seconds** is bar animation, not a separate attack or a contradiction of the log's 30% → 0%. The 324-second HUD reads 0%, followed by the 325.5-second faint message. Opponent percentage values do not reveal exact opponent HP or damage.

The log's generic “训练家” send-out messages are attributed to the opponent by the matching withdrawal/faint sequence and video. Psychic Terrain and rain can coexist: one is terrain, the other weather. The two-stat decrease remains one log entry, and ability/weather/terrain announcements remain separate entries; repeated scroll views are deduplicated. No stat-stage magnitude, item consumption state, hidden move choice, speed ordering, or unshown action is inferred.

The top view at 374 seconds and bottom view at 372 seconds establish the visible Turn 2 list boundaries. No Turn 1 tab was opened in these frames. Events after the log closes at approximately 381 seconds belong to subsequent playback and are outside this reconstruction, including the Rillaboom return visible at 386–393 seconds. This report makes no claim that all turns or all possible UI event types have been captured.

## Artifacts and validation

- [Structured extraction and alignment](M2-battle-log-alignment.json): 20 ordered events, original cache frame paths, separate log/battle observation times, extraction command, and SHA-256 hashes of the saved report evidence.
- [Saved evidence directory](M2-battle-log-evidence): six lossless log-panel crops and 20 battle screenshots. Battle screenshots are JPEG copies for report size; the original extracted PNGs remain in the local cache.
- Original survey cache and earlier milestone reports remain unchanged. No application code, architecture, commit, or push was added.

Validation: manually reviewed the overlapping log views and battle contact sheets, then inspected the cited full-resolution frames; checked event order/count, evidence-file existence, image hashes, and `git diff --check`. Application tests are unnecessary for this report-only change. This is a manually verified sample, not an automated event-extraction benchmark.
