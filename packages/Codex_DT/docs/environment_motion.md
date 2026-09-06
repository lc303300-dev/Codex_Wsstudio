# 环境动态策略（environment-motion/v1）

这是导演—语料—提示词流程中的一个窄职责编译器：它只处理视觉识别结果中已经出现的植物、水面、倒影等环境元素，不负责镜头、景别、焦段、曝光、色彩、胶片质感或主体动作。

## 接入顺序

1. 视觉识别把结果写入 manifest 的 `visual` 字段。
2. 执行 `scripts/compile_environment_motion.py --batch <batch>`。
3. 仅当 `environment_motion.detected=true` 时，为该 manifest 检索环境动态语料。
4. 执行 `scripts/update_forge_matches.py --batch <batch>`；环境动态 manifest 的语料会经过句子级清洗。
5. 导演层把 `environment_motion.prompt_section_zh` 放在环境动态段落，不覆盖导演已经确定的镜头段落。

## 语料边界

环境动态语料必须至少描述以下一项：风/微风导致的枝叶摆动、水面波纹/流动、倒影或反射随表面运动的变化。以下内容不属于本功能，必须删除：

- 镜头、运镜、推拉摇移、跟拍、航拍、景别、焦段、广角/长焦；
- 曝光、景深、胶片颗粒、色调、构图、电影感等画面风格建议；
- 与植物/水面运动无关的人物、道具、剪辑、音乐和通用动作建议。

清洗器会丢弃没有环境证据的记录，并从混合记录中移除通用建议句。清洗后的记录写入 `forge.matches` 时带有 `environmental_motion_only=true`，便于审计。

## 手动调用

```powershell
python scripts/compile_environment_motion.py --manifest manifests/<batch>/<item>.json
python scripts/update_forge_matches.py --batch <batch>
```

如果识别结果没有匹配元素，编译器输出空策略，后续导演提示词保持原有行为。
