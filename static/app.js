document.documentElement.classList.add("js-enabled");

const favoriteButton = document.querySelector(".favorite-toggle");

if (favoriteButton) {
    favoriteButton.addEventListener("click", async () => {
        favoriteButton.disabled = true;
        try {
            const response = await fetch("/api/favorite", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    root: Number(favoriteButton.dataset.root),
                    path: favoriteButton.dataset.path,
                }),
            });
            if (!response.ok) {
                throw new Error(`Favorite request failed: ${response.status}`);
            }

            const result = await response.json();
            favoriteButton.classList.toggle("is-favorite", result.favorite);
            favoriteButton.setAttribute("aria-pressed", String(result.favorite));
            const label = result.favorite ? "取消收藏" : "收藏视频";
            const icon = favoriteButton.querySelector(".favorite-icon");
            const text = favoriteButton.querySelector(".favorite-label");
            if (icon) icon.textContent = result.favorite ? "★" : "☆";
            if (text) text.textContent = label;
            favoriteButton.setAttribute("aria-label", label);
            favoriteButton.title = label;
        } catch (error) {
            favoriteButton.title = "操作失败，请重试";
            console.error(error);
        } finally {
            favoriteButton.disabled = false;
        }
    });
}
