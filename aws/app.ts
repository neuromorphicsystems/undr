const sizeToString = size => {
    if (size < 1000) {
        return `${size.toFixed(0)} B`;
    }
    if (size < 1000000) {
        return `${(size / 1000).toFixed(2)} kB`;
    }
    if (size < 1000000000) {
        return `${(size / 1000000).toFixed(2)} MB`;
    }
    if (size < 1000000000000) {
        return `${(size / 1000000000).toFixed(2)} GB`;
    }
    return `${(size / 1000000000000).toFixed(2)} TB`;
};

const location = "https://undr.s3.ap-southeast-2.amazonaws.com/"; // @DEV replace with window.location

window.addEventListener("DOMContentLoaded", () => {
    const filesElement = document.getElementById("files");
    const directoriesElement = document.getElementById("directories");
    const request = new XMLHttpRequest();
    request.onload = () => {
        window.response = request.response; // @DEV
        const directories = request.response.querySelectorAll("CommonPrefixes");
        filesElement.replaceChildren(
            ...Array.prototype.map.call(
                request.response.querySelectorAll("Contents"),
                file => {
                    const fileElement = document.createElement("div");
                    const nameElement = document.createElement("a");
                    nameElement.innerHTML = file.querySelector("Key").innerHTML;
                    fileElement.appendChild(nameElement);
                    const sizeElement = document.createElement("span");
                    const size = parseInt(file.querySelector("Size").innerHTML);
                    sizeElement.innerHTML =
                        size < 1000
                            ? `${size} B`
                            : `${size} B (${sizeToString(size)})`;
                    fileElement.appendChild(sizeElement);
                    return fileElement;
                }
            )
        );
    };
    request.open(
        "GET",
        "https://undr.s3.ap-southeast-2.amazonaws.com/?list-type=2&delimiter=/&encoding-type=url&max-keys=1000000&prefix=dvs09/"
    );
    request.responseType = "document";
    filesElement.replaceChildren();
    directoriesElement.replaceChildren();
    request.send();
});
