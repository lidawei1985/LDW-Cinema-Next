package com.ldw.cinema.next.search

/**
 * 联想词库（人名 / 剧名 -> 海报）。
 *
 * 匹配规则：
 *  - 中文名包含输入（如输入“李”匹配“李丽珍”）；
 *  - 拼音首字母前缀（如输入“L”匹配 李(Li)/刘(Liu)/柳(Liu) → 李丽珍、李小龙、刘德华、柳岩）；
 *  - 剧名包含输入。
 *
 * 生产环境：该词库可由后端 combined.json 的搜索结果动态扩充（[SearchSuggestionManager.loadFromJson]），
 * 这里内置一份种子数据，保证离线也能联想。
 */
data class PersonEntry(
    val name: String,
    val pinyin: String,        // 全拼，如 "lilizhen"
    val initial: String,       // 首字母，如 "llz"
    val kind: String,          // "actor" / "drama"
    val posterUrl: String = "" // 为空时 UI 用首字占位图
)

object PersonIndex {
    /** 种子数据：覆盖用户示例（L → 李丽珍/李小龙/刘德华/柳岩）。 */
    val seed: List<PersonEntry> = listOf(
        PersonEntry("李丽珍", "lilizhen", "llz", "actor"),
        PersonEntry("李小龙", "lixiaolong", "lxl", "actor"),
        PersonEntry("刘德华", "liudehua", "ldh", "actor"),
        PersonEntry("柳岩", "liuyan", "ly", "actor"),
        PersonEntry("林青霞", "linqingxia", "lqx", "actor"),
        PersonEntry("梁朝伟", "liangchaowei", "lcw", "actor"),
        PersonEntry("成龙", "chenglong", "cl", "actor"),
        PersonEntry("周星驰", "zhouxingchi", "zxc", "actor"),
        PersonEntry("张曼玉", "zhangmanyu", "zmy", "actor"),
        PersonEntry("古天乐", "gutianle", "gtl", "actor"),
        PersonEntry("琅琊榜", "langyabang", "lyb", "drama"),
        PersonEntry("亮剑", "liangjian", "lj", "drama"),
        PersonEntry("流星花园", "liuxinghuayuan", "lxhy", "drama"),
        PersonEntry("三国演义", "sanguoyanyi", "sgry", "drama")
    )

    private val extra = mutableListOf<PersonEntry>()

    fun all(): List<PersonEntry> = seed + extra

    /** 由后端搜索结果动态扩充（去重按 name）。 */
    fun extend(entries: List<PersonEntry>) {
        val seen = all().map { it.name }.toSet()
        entries.filter { it.name !in seen }.let { extra.addAll(it) }
    }
}
