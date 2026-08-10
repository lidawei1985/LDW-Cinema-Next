// 根构建脚本（仅声明仓库/插件版本；具体模块见 app/build.gradle.kts）。
// 说明：LDW-Cinema-Next 的自定义模块（update/search/core）设计为叠加在
// TVBox / CatVod 底座之上——底座提供播放器与 spider 运行时，本仓库提供
// 更新 / 搜索联想 / 一致性路由 / 自维护片源接入。CI 见 .github/workflows/build.yml。
plugins {
    id("org.jetbrains.kotlin.android") version "1.9.24" apply false
    id("com.android.application") version "8.5.2" apply false
}
