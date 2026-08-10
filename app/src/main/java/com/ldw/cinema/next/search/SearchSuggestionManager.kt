package com.ldw.cinema.next.search

import org.json.JSONArray
import org.json.JSONObject

/**
 * 搜索联想管理器（规格 3）。
 *
 * 输入联想：输入 "L" 即时返回 李丽珍 / 李小龙 / 刘德华 / 柳岩 等，并附带对应海报。
 * 支持：人名、剧名、海报三要素同步呈现。
 */
object SearchSuggestionManager {

    data class Suggestion(
        val name: String,
        val kind: String,     // actor / drama
        val posterUrl: String,
        val hint: String      // 拼音/首字母提示
    )

    /**
     * @param query 用户输入（中文或拼音/首字母，大小写不敏感）
     * @param limit 返回条数
     */
    fun suggest(query: String, limit: Int = 10): List<Suggestion> {
        val q = query.trim().lowercase()
        if (q.isEmpty()) {
            // 空输入：返回热门
            return PersonIndex.all().take(limit).map(::toSuggestion)
        }
        return PersonIndex.all()
            .filter { e ->
                e.name.contains(query.trim(), ignoreCase = true) ||
                e.pinyin.startsWith(q) ||
                e.initial.startsWith(q) ||
                e.pinyin.contains(q)
            }
            .take(limit)
            .map(::toSuggestion)
    }

    /** 从后端 JSON 扩充词库（后端搜索接口返回的人名/剧名/海报）。 */
    fun loadFromJson(json: String) {
        runCatching {
            val arr = JSONArray(json)
            val list = mutableListOf<PersonEntry>()
            for (i in 0 until arr.length()) {
                val o = arr.getJSONObject(i)
                list.add(
                    PersonEntry(
                        name = o.optString("name"),
                        pinyin = o.optString("pinyin", o.optString("name")),
                        initial = o.optString("initial", ""),
                        kind = o.optString("kind", "actor"),
                        posterUrl = o.optString("posterUrl")
                    )
                )
            }
            PersonIndex.extend(list)
        }
    }

    private fun toSuggestion(e: PersonEntry) = Suggestion(
        name = e.name,
        kind = e.kind,
        posterUrl = e.posterUrl,
        hint = e.initial.uppercase()
    )
}
