# Seedance 2.0 プロンプト構築Skill

[English](README.md)

Seedance 2.0専用の、根拠管理つきCodex Skillです。Dreamina、BytePlus ModelArk、Volcengine、Fal、Higgsfieldなどの利用面に合わせて、制作に使えるプロンプト、素材表、設定、検証結果を組み立てます。

毎回「画像は`@Image 1`」「動画は`@Video 1`」と説明する必要はありません。人物画像、商品画像、カメラ参考動画、声の参考音声などを伝えるだけで、素材ごとの役割と転写禁止要素まで整理します。

単なる作例集ではなく、Seedance 2.0向けの**参照素材対応プロンプトcompiler + validator**です。

## 特徴

- Seedance 2.0 Standardを既定値として使用
- 日本語promptと日本語台詞に対応
- Text-to-Video、開始frame、開始＋終了frame、複数素材参照、編集、延長、clip接続
- Image / Video / Audioごとの役割分離
- `vibe-explore` / `balanced` / `precision`の3系統
- 複雑な映像は`Shot 1 / Shot 2 / Shot 3`で時系列化
- 人物増殖、役割混在、shot過密、camera過積載、字幕・logo・audio矛盾を検査
- 公式、provider仕様、市場実測、heuristicを別レベルで管理

## 表記の自動変換

内部では`image:1`のような共通IDで管理し、利用面に合わせて変換します。

| 利用面 | Image 1 | Video 1 | Audio 1 |
|---|---|---|---|
| Dreamina | `@Image 1` | `@Video 1` | `@Audio 1` |
| Volcengine / Jimeng中国語UI | `@图片1` | `@视频1` | `@音频1` |
| BytePlus API向け文章 | `[Image 1]` | `[Video 1]` | `[Audio 1]` |
| Fal | `@Image1` | `@Video1` | `@Audio1` |
| MuAPI | `@image1` | `@video1` | `@audio1` |

prompt内の表記と、APIの`first_frame`や`reference_image`は別物です。厳密な開始frameや一般参照を混同しないように処理します。

## インストール

PowerShell:

```powershell
git clone https://github.com/mqrox/seedance-2.0-prompt-skill.git
Copy-Item -Recurse -Force .\seedance-2.0-prompt-skill\build-seedance2-prompts "$HOME\.codex\skills\"
```

macOS / Linux:

```bash
git clone https://github.com/mqrox/seedance-2.0-prompt-skill.git
cp -R seedance-2.0-prompt-skill/build-seedance2-prompts ~/.codex/skills/
```

同名の旧skillがある場合は、先にbackupしてください。

## 使い方

通常のSeedance 2.0依頼でも自動起動できます。明示する場合:

```text
$build-seedance2-prompts

Image 1は女性モデル、Image 2は商品のpackshot、Video 1からはcameraだけ、
Audio 1からは声質だけを使ってください。12秒・9:16の高級化粧品CM。
日本語ナレーションは「光は、肌の奥から。」
```

局所編集:

```text
$build-seedance2-prompts

FalのSeedance 2.0で、Video 1の4〜6秒にある青いmugだけを白い陶器mugへ変更。
人物、手、camera、lighting、元audio、8秒の尺は完全維持。
```

素材なしの短編:

```text
$build-seedance2-prompts

雨の夜の駅で別れた成人二人が、一瞬だけ振り返る短編。素材なし。SNS縦型。
大げさに泣かず、胸に残る演出にしてください。
```

## 根拠

現行のByteDance Seed / BytePlus / Volcengine資料を最優先し、providerの実際のschema、市場で支持される実装、制作者の検証結果を区別して採用しています。

- [Seedance 2.0公式model page](https://seed.bytedance.com/en/seedance2_0)
- [BytePlus Prompt Guide](https://docs.byteplus.com/en/docs/ModelArk/2222480)
- [BytePlus API](https://docs.byteplus.com/en/docs/ModelArk/1520757)
- [Volcengine Prompt Guide](https://www.volcengine.com/docs/82379/2222480?lang=zh)
- [Volcengine公式`sd2-pe` skill](https://arkdoc.tos-cn-beijing.volces.com/files/video-generation/SKILL.md)

詳しくは[evidence ledger](build-seedance2-prompts/references/evidence-ledger.md)を参照してください。

## 注意

このrepositoryは非公式の独立open-source projectです。ByteDance、Seed、Dreamina、BytePlus、Volcengine、Fal、Higgsfield等との提携・承認関係を示すものではありません。

[MIT License](LICENSE) © 2026 Hideaki Nagata (`mqrox`).
