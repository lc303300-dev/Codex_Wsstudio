# Curated Prompt Examples

These examples are scaffolds for structure, not copy targets. Study the section grammar each prompt uses — timestamps, bold headers, bracket sections, bilingual tags — then apply that same grammar to your own subject matter. A short prompt that nails its concept-only grammar can be as effective as a long storyboard prompt that specifies every lens and beat. Select the structural pattern that matches the complexity and fidelity requirements of your scene, then rebuild it around your character, setting, and action.

Use these entries to answer the question: "What kind of structure does this type of scene need?" The entries below cover ultra-short concept frames, timestamped multi-beat storyboards, reference-image anchored setups, bilingual tagged structures, bracket-section cinematic briefs, and game-UI narrative forms. The full source index is searchable with `scripts/search.py` for additional examples by style, source, length, or subject.

---

### Mortal Kombat with World Leaders

**Source**: The Dor Brothers — https://x.com/thedorbrothers/status/2021203121024926171
**Length**: 76 chars | **Demonstrates**: Ultra-short IP-reference prompt — borrows an existing visual grammar in one sentence, trusting the model to supply staging, lighting, and character design from a named franchise.

"Mortal Kombat gameplay footage but the characters are famous world leaders"

---

### Action Hero Combat Scene

**Source**: Ava AI Labs — https://x.com/TheAva_AI/status/2040901121720369231
**Length**: 95 chars | **Demonstrates**: Ultra-short concept-only prompt using a 5-tag grammar (setting, action, style, camera, beat); functions as an abstract blueprint where every element is a category hint, not a scene description.

Action hero in neon ruined city, energy blade combat, cinematic camera, fast cuts, boss reveal.

---

### Anime Scene of Lumine from Genshin Impact

**Source**: Kokoboy — https://x.com/Kokoboy886711/status/2021421581558481040
**Length**: 216 chars | **Demonstrates**: Single continuous-action sentence that chains subject → setting → movement → physical consequence, with elemental and material detail encoded inline rather than in separate headers.

Anime scene of Lumine from Genshin Impact dashing across a shattered temple courtyard, leaping into a mid-air somersault and delivering a spiral sword slash that sends glowing elemental energy and stone debris flying

---

### Cinematic Widescreen Transformation Scene with Reference Image

**Source**: Aivoxy — https://x.com/aivoxyy/status/2032425095206182971
**Length**: 275 chars | **Demonstrates**: Bold-header structured prompt (Face / Clothing / Environment / Visual Style) with explicit @Image1 reference integration and a no-beautification fidelity clause — the minimal viable form of reference-anchored scene setup.

Face: Refer to @Image1 (upload your image). Facial structure and features must match exactly with no beautification.
Clothing: worn, weathered jacket.
Environment: black soil ground beside a lake under a dull grey sky.
Visual Style: cinematic widescreen transformation scene.

---

### Toaster Rocket Jumpscare

**Source**: Marin — https://x.com/MarinMethod/status/2049140113343394003
**Length**: 476 chars | **Demonstrates**: Grounded everyday-physics comedy prompt using handheld "home video" style framing; a short kitchen scene demonstrating that unexpected physical comedy can be conveyed with setting + character reaction + camera style, no timeline required.

A realistic shot of an old man in a cozy kitchen being jumpscared when his toaster launches the bread five feet into the air like a rocket. Handheld "home video" style capturing his genuine look of shock and the bread hitting the ceiling.A realistic shot of an old man in a cozy kitchen being jumpscared when his toaster launches the bread five feet into the air like a rocket. Handheld "home video" style capturing his genuine look of shock and the bread hitting the ceiling.

---

### Cyberpunk Rooftop Pursuit

**Source**: Kiber Alla — https://x.com/Kiber_Alla/status/2045806507229392998
**Length**: 1417 chars | **Demonstrates**: Timestamp-only timeline structure (0:00–0:02 through 0:14–0:15) with per-beat shot type, subject action, and environmental detail, closed by an explicit anatomical-integrity rule that constrains model behavior during extreme motion.

0:00-0:02: Close-up of her face as she regains balance, then a quick wide shot. She looks up at a dark hatch. 
0:02-0:05: Rapid jump-cuts: she crouches, then leaps with a powerful burst of energy through the ceiling opening. First-person view looking up, followed by a side view of her soaring through the gap. 
0:05-0:07: She lands on a rainy skyscraper roof, the city neon reflecting in puddles. Cut to the vampire below, his face twisted in a grin, saying: "Where are you going, baby?" as he instantly begins to follow. 0:07-0:08 Extreme wide shot as she leaps across a narrow gap between buildings. 
0:08-0:09 The pale vampire with fangs sprint-climbs a parallel wall with supernatural speed. 
0:09-0:10 Cyborg woman: Parkour vault over an industrial HVAC unit, blue sparks arm scraping the surface. 
0:10-0:11 Side-view tracking shot as the vampire performs a massive leap over a glowing neon billboard. 
0:11-0:12 Low-angle reverse shot from her POV looking back: the vampire gains ground. 
0:12-0:13 Dutch angle shot showing both running past the camera. 
0:13-0:14 Handheld camera shot from the vampire's POV. 
0:14-0:15 Final shot: she dive off a roof. 
Anatomical Integrity Rule: Strictly maintain all human-cyborg body proportions. Zero tolerance for limb stretching, facial melting, or anatomical mutations during extreme jumps and fast movements. Gritty cyberpunk, rainy night, cinematic motion blur, 8k.

---

### Space to Cafe Transition Shot

**Source**: Shami — https://x.com/ShamiWeb3/status/2047872312683434203
**Length**: 1260 chars | **Demonstrates**: Named timeline with labeled phase headers (Scene / Subject / Timeline / Camera & Style / Audio) and timestamp beats, using @img1 reference integration and explicit speed-ramp instruction (slow → ultra-fast → smooth stop) to control the single-take arc.

Scene:
A seamless ultra-cinematic one-take shot transitioning from deep space to an intimate café moment, emphasizing scale, speed, and immersion.

Subject:
@img1 — a young woman at an open-air café named "YAPPER", wearing denim shorts and a white shirt, casually eating a hamburger with a drink.

Timeline (15s):

0–4s — Space to Earth:
Wide shot of Earth in deep space. Camera accelerates forward; Earth grows rapidly with subtle light streaks and atmospheric glow.

4–8s — Atmosphere Entry:
Camera pierces atmosphere. Clouds rush past, continents sweep below with strong motion blur and fast descent.

8–11s — City Dive:
Sharp dive into a city. Skyscrapers streak past, transitioning into smooth street-level motion with realistic urban flow.

11–12s — Café Lock:
Camera targets café with glowing "YAPPER" sign. Rapid but smooth deceleration, tones shift warmer.

12–15s — Final Shot:
Camera settles on @img1. She casually eats, takes a bite, adjusts posture, and looks at her food—calm and unaware of the cosmic journey.

Camera & Style:

One continuous shot, no cuts.
Speed ramp: slow → ultra-fast → smooth stop.
Wide lens → natural cinematic lens.
Subtle handheld realism at end.

Audio:

Space ambience → intense descent → city noise → soft café sounds.

---

### Sci-Fi Transformation Scene

**Source**: WasifAI — https://x.com/doctorwasif/status/2038846359399506177
**Length**: 1218 chars | **Demonstrates**: Paragraph-narrative form with an opening lens/film-stock declaration, followed by a single-take prose storyboard where each paragraph is one transformation beat — no headers required when prose rhythm provides the pacing structure.

65mm IMAX, ultra-wide anamorphic lens, heavy film grain, strong lens flares. Eclipse-like atmosphere with dense gray fog. Only light source is an internal orange-red glow from the character, like a dying star.
Single-take 15s:
A dust-covered man stands alone in a wasteland. Handheld camera circles him in a 360° orbit with slight shake from heat. He slowly raises his hand—fingertips turn semi-transparent, air distorts.
His body convulses under pressure. Glowing golden cracks spread beneath his skin, bones crack. Purple-black smoke with blue electrical arcs bursts from his spine. Deep fractures leak liquid gold.
Floating metal debris is pulled toward him. Rusted black armor plates slam into his body with sparks, forming uneven armor—cracked shoulders and a chest plate revealing a molten core.
Red metal spreads across his face, forming a mask. His eyes collapse, then ignite with blue electric light, one flickering. Two large black horns emerge with faint purple flames.
Final: he raises his hand, forming a blue flame like a miniature black hole. He slams the ground—spiraling gravity shockwave destroys nearby ruins. Silence. Broken black wings extend. He lifts his head, blue eyes glowing through the fog.

---

### Stealth Mini-Game Heist Video Prompt

**Source**: KANA — https://x.com/KanaWorks_AI/status/2048407984456519965
**Length**: 1527 chars | **Demonstrates**: Game-UI narrative form — scene described as observed gameplay with embedded companion dialogue-box beats and a diegetic UI event (boss music trigger, battle-screen transition, on-screen calligraphy) to produce game-genre visual output.

A mini-game style stealth theft scene, with exaggerated, humorous actions and expressions. No subtitles. High definition, 30fps.
A massive tengu-like yokai is drunk, asleep deep inside a mountain cave, clutching a large sake jar in its arms, snoring loudly as it sleeps. The cave is filled with numerous sake jars, with several particularly fine ones placed around the creature.
In the foreground, the player character is seen from behind, crouching low with one hand on the ground, quietly approaching. They begin feeling around the sake jars near the sleeping yokai. A glowing effect appears.
Cut to a front-facing shot: the player character struggles to lift a large sake barrel. A companion dialogue box pops up.
The player character crouches again, continuing to search around. The tengu snores heavily, still fast asleep. Another glow effect appears.
The player character stands up with difficulty, holding a large sake barrel. A companion dialogue box appears again.
Carrying the oversized barrel, the player character turns and runs toward the cave entrance.
At that moment, intense boss battle music—typical of an action combat game—suddenly kicks in. A companion dialogue box appears.
The player character hastens their pace, running in a zigzag pattern, struggling to move forward while carrying the heavy load.
Then the scene forcefully transitions into a battle interface. The tengu awakens, waving a feather fan and striking a flashy, dramatic combat pose.
On screen, large bold black calligraphy appears: "バトル開始"

---

### Transformer Transformation Cinematic Sequence

**Source**: nft0755.milady 发财 — https://x.com/zlb2017/status/2024858145546555522
**Length**: 1597 chars | **Demonstrates**: Chinese 分镜 (storyboard) header structure — each beat labeled with a scene number, Chinese title, and timestamp range, followed by an English shot description with photographic specs (shot type, angle, lens quality) embedded per beat.

分镜 1：动力重组：车尾裂变 (0-4s)
动作： Close-up tracking shot. A dusty muscle car accelerates. Suddenly, the rear chassis violently splits, expanding into gigantic hydraulic mechanical legs. The rear tires reconfigure into jagged metal heels. These legs slam onto the bridge deck, crushing the asphalt with a massive sense of weight. Blue sparks and white smoke erupt from the friction. High-frequency vibration, 8K photorealistic.

分镜 2：躯干扩张：钢铁脊梁 (4-8s)
动作：The transformation ripples forward. The car's roof and hood fold and stack into a massive mechanical torso and armored shoulders. The interior of the car deconstructs, exposing a glowing power core. The titan stands nearly 15 meters tall, its metal spine extending and locking with a loud mechanical clank. Handheld shaky cam, low angle looking up at the growing giant.

分镜 3：正面武装：胸口炮仓 (8-12s)
动作：Extreme close-up on the chest armor plates. The heavy plating slides open in a complex clockwork sequence, revealing a colossal kinetic energy cannon nestled in the torso. Blue plasma arcs dance around the rifled barrel. The surrounding air begins to shimmer from intense thermal energy. The camera captures the intricate clicking of locking mechanisms.

分镜 4：终极裁决：毁灭一击 (12-15s)
动作：The cannon fires a devastating, blinding cyan energy beam directly from the chest. The massive recoil forces the titan to dig its metal claws into the bridge. The beam pierces through abandoned vehicles, causing them to melt and explode instantly. A shockwave ripples through the air, shattering remaining glass. Epic cinematic wide shot, masterwork, apocalyptic aesthetic.

---

### Detailed Seedance 2.0 Prompt for a Dancing Fox Girl

**Source**: レイリア — https://x.com/Reiria123/status/2041118339393826933
**Length**: 2015 chars | **Demonstrates**: Bilingual JP/EN tagged section structure (【主体 / Subject】 / 【アクション / Action】 / 【カメラ / Camera】 / 【スタイル / Style】 / 【サウンド / Sound】) with per-section motion-stability instructions and a reference-image consistency clause at the top.

Use @Image1 as the character reference. Keep character design, hairstyle, ears, tail, outfit, and colors perfectly consistent.

【主体 / Subject】

A blue-haired fox girl with long flowing hair, large fluffy fox ears, and a huge fluffy tail.
She wears a shrine-maiden inspired outfit with loose sleeves and a short skirt.
She stands in a Japanese shrine setting with a red torii gate, autumn leaves falling around her.
Her expression is playful, energetic, slightly teasing.

【アクション / Action】

She performs an energetic, bouncy dance with frequent jumping motions.

Repeated light jumps in rhythm (ぴょんぴょん)
Knees bend deeply before each jump for natural motion
Hair, sleeves, and tail bounce dynamically with physics
Tail sways with exaggerated follow-through motion
Spins mid-jump once (360° quick spin)
Lands softly and immediately transitions into next jump
Arms swing wide, then pull inward for momentum
Ends with a high jump and playful pose on landing

👉 重要安定化指示

Clear leg bending and landing weight control
Natural gravity and smooth jump arcs
No body distortion during airtime
Tail follows delayed secondary motion
【カメラ / Camera】
Landscape 16:9, 15 seconds
Start: full-body wide shot (全身見せてジャンプ確認)
Slight low-angle to emphasize jump height
Gentle tracking to follow vertical movement
Subtle handheld bounce synced with jumps
Mid-section zoom during spin jump
End: slight push-in as she lands final pose
【スタイル / Style】
High quality 2D anime animation
Smooth, high frame consistency
Bright autumn color palette (red, orange, gold leaves)
Soft sunlight filtering through trees
Motion emphasis on cloth physics and tail volume
Clean linework, slightly soft shading
Light bloom and depth of field
【サウンド / Sound】

Upbeat, hyper-energetic J-pop / electro dance track (~170 BPM)

Bouncy bass and punchy kick drum
Bright synth melodies
Clap and snare accents on jumps
Cute but energetic female vocal (short phrases / chants)
Fox-like playful "hey!" or "yo!" vocal accents
Subtle ambient shrine atmosphere (wind + leaves)

---

### Biotech Alien Suit Metamorphosis

**Source**: Iqra Saifi — https://x.com/IqraSaifiii/status/2048094042983133237
**Length**: 1999 chars | **Demonstrates**: Phase-labeled prose structure (Phase 1 / Phase 2 / Phase 3) with an opening visual foundation block (fidelity clause + style + environment), per-phase camera work embedded inline, and anti-pattern instructions ("Eschew toy-like assembly") that constrain model behavior.

Visual & Atmospheric Foundation Facial Fidelity: The output must adhere strictly to the uploaded reference photo. No digital "beautification," skin smoothing, or alteration of bone structure. The character remains raw and human. Style: Realistic, gritty, and oppressive. Think "biotechnology meets alien machinery"—organic textures that feel cold and functional rather than fantastical. Environment: An expansive, overcast outdoor space. The color palette is dominated by gray-blues and muted tones. A constant wind should be visible through the movement of the character's clothing. Phase 1: Pre-Transformation (The Calm) Attire: A heavy black leather trench coat over a black shirt. Grooming: Bangs remain low, obscuring the forehead to maintain a gloomy, composed, and introverted silhouette. The Belt: A minimalist, high-end piece of matte-finished metal. It houses an "alien energy core" that looks like a scientific specimen rather than a commercial product. Camera Work: Medium Shot: Starts at a fixed 30-degree side profile. Movement: A slow, hypnotic rotation toward the center while gently pushing in (dolly-in). No cuts. Action: The character begins with their head down, slowly lifting it to face the camera as their right hand grips the belt. Phase 2: The Metamorphosis (The Storm) Audio/Music: Heavy, low-frequency mechanical hums paired with a tense, atmospheric score. Visual Effects: * Energy: Dark red light bleeds out, intertwined with swirling black mist and jagged black particles. Process: As the energy surrounds them, the body performs a slight, stiff rotation and then freezes. Execution: Eschew "toy-like" assembly. The suit doesn't click together; it manifests through the mist and particles as a biological shift. Phase 3: The Final Form  Suit Composition: A fusion of black biological tissue and alien alloys. It should look "living" and "growing," with pulsating textures. Details: Faintly glowing red vascular lines trace the suit,culminating in deep red menacing eyes

---

### Cinematic Post-Apocalyptic Survival Sequence

**Source**: Cyber AI Creator — https://x.com/noman23761/status/2041405260762419692
**Length**: 2047 chars | **Demonstrates**: Bracket-section structure ([CINEMATIC SETUP] / [TIMELINE SECOND BY SECOND] / [STYLE & QUALITY BOOSTERS]) with second-by-second shot list using named shot types (ECU, Macro Cut, OTS, POV), a character description block, and a closing quality-booster tag list.

"[CINEMATIC SETUP] Genre & Mood: Gritty Post-Apocalyptic Survival. Tense, visceral, and hyper-realistic. Film Stock & Lens: Shot on 35mm anamorphic lens, f/2.8 for shallow depth of field. Teal-orange desaturated color grade with earthy, dusty undertones. Lighting & Atmosphere: Dramatic volumetric Golden Hour light with heavy dust motes and heat haze. Character Description: An athletic woman in her late 20s, wearing weathered tactical leather armor and dirt-smudged skin. Her hair is wind-blown and messy; her expression is one of intense, lethal focus. Audio Style: Immersive spatial sound design. Detailed SFX of bowstring tension, rhythmic heavy breathing, wind howling through the canyon, and a high-velocity "thwack" on impact. [TIMELINE SECOND BY SECOND] 0-3s: [Extreme Close-up (ECU)] High-angle shot of the woman's face as she aims a mechanical compound bow. The bowstring is pulled taut against her cheek. Movie-level realistic facial features, no deformation, stable throughout. 3-4s: [Macro Cut] Extreme close-up of her iris. The pupil dilates sharply as she locks onto her target. Realistic light reflections in the eye. 4-8s: [Over-the-shoulder (OTS) Shot] The camera sits behind her shoulder on a jagged cliff edge. In the valley below, a herd of mutated, post-apocalyptic Cape Buffalo with thickened grey hide and jagged horns graze peacefully. Smooth camera push-in. 8-10s: [The Release & POV] She releases the arrow. Fast Tracking POV shot following the arrowhead at maximum velocity. Intense motion blur on the passing rocky environment as the arrow slices the air. 10-15s: [Impact & Wide Shot] The arrow strikes the lead beast in the flank with realistic physics. The animal collapses heavily into the dust. The rest of the herd panics and scatters in a chaotic wide shot. Sound fade to the howl of the wind. [STYLE & QUALITY BOOSTERS] Photorealistic 8K, ultra-detailed textures (skin pores, rusted metal, animal fur), cinematic lighting, perfect motion blur, high dynamic range, no artifacts, coherent multi-subject motion."

---

*For additional examples across all prompt lengths, styles, and subjects, search the full source index with `scripts/search.py`.*
