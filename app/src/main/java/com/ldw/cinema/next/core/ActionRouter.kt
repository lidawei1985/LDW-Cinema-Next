package com.ldw.cinema.next.core

/**
 * 集中动作路由（规格 2：功能一致性）。
 *
 * 所有界面按钮/入口都通过 [dispatch] 触发，保证：
 *  - 按键 id 与界面标识（label）严格对应；
 *  - 分类（category）与内容精准匹配；
 *  - 未注册的动作在开发期即可被发现（[assertAllBound]）。
 */
object ActionRouter {

    data class ActionDescriptor(
        val key: String,
        val label: String,
        val category: String
    )

    private val registry = LinkedHashMap<String, ActionDescriptor>()
    private val handlers = HashMap<String, (payload: Any?) -> Unit>()

    /** 注册一个界面动作（按键标识 + 文案 + 所属分类）。 */
    fun register(key: String, label: String, category: String) {
        registry[key] = ActionDescriptor(key, label, category)
    }

    /** 绑定处理函数。 */
    fun bind(key: String, handler: (payload: Any?) -> Unit) {
        handlers[key] = handler
    }

    /** 分发动作。返回是否成功路由。 */
    fun dispatch(key: String, payload: Any? = null): Boolean {
        val h = handlers[key] ?: return false
        h(payload)
        return true
    }

    /** 按分类取动作列表（用于菜单/分类页一致性校验）。 */
    fun byCategory(category: String): List<ActionDescriptor> =
        registry.values.filter { it.category == category }

    /** 开发期断言：所有注册动作都有处理函数，否则抛错。 */
    fun assertAllBound() {
        val unbound = registry.keys.filter { it !in handlers }
        check(unbound.isEmpty()) { "未绑定的动作: $unbound" }
    }

    fun size(): Int = registry.size
}
