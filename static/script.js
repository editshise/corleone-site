function openMenu() {
    document.getElementById("sideMenu").classList.add("active");
    document.getElementById("overlay").style.display = "block";
}

function closeMenu() {
    document.getElementById("sideMenu").classList.remove("active");
    document.getElementById("overlay").style.display = "none";
}