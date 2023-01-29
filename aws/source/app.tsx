import * as React from "react";
import * as ReactDOM from "react-dom/client";
import styled, {
    ThemeProvider,
    DefaultTheme,
    createGlobalStyle,
} from "styled-components";
import * as theme from "./theme";
import Content from "./components/content";
import Select from "./components/select";
import Undr from "./icons/undr.svg";
import UndrSmall from "./icons/undr-small.svg";
import Wsu from "./icons/wsu.svg";

const GlobalStyle = createGlobalStyle`
    body {
        background-color: ${props => props.theme.background2};
    }
`;

const StyledMain = styled.div`
    display: flex;
    flex-direction: column;
    height: max(100vh, 500px);
    background-color: ${props => props.theme.background0};
    font-family: Helvetica, Arial, sans-serif;
    font-size: 14px;
    font-weight: 300;
    color: ${props => props.theme.content0};
`;

const Banner = styled.div`
    flex-shrink: 0;
    display: flex;
    align-items: center;
    background-color: ${props => props.theme.background2};
    padding: 20px;
    gap: 20px;
    @media (max-width: 512px) {
        flex-direction: column;
    }
`;

const BannerLogo = styled.div`
    height: 120px;
    display: block;
    @media (max-width: 512px) {
        display: none;
    }
    & > svg {
        display: block;
        height: 100%;
    }
`;

const BannerContent = styled.div`
    width: 100%;
`;

const BannerTitle = styled.div`
    display: flex;
    @media (max-width: 512px) {
        display: none;
    }
`;

const BannerTitleNarrow = styled.div`
    display: none;
    @media (max-width: 512px) {
        display: flex;
        gap: 20px;
        align-items: center;
        justify-content: center;
    }
`;

const BannerLogoSmall = styled.div`
    height: 90px;
    & > svg {
        display: block;
        height: 100%;
    }
`;

const BannerTitleContent = styled.div`
    font-weight: 500;
    font-size: 20px;
`;

const BannerDescription = styled.div`
    padding-top: 20px;
    padding-bottom: 20px;
    text-align: justify;
    hyphens: auto;
`;

const Link = styled.a`
    display: block;
    color: ${props => props.theme.content0};
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    text-decoration: none;
    font-weight: 500;
    &:hover,
    &:active {
        color: ${props => props.theme.link};
        text-decoration: underline;
    }
`;

const Navbar = styled.div`
    height: 50px;
    flex-shrink: 0;
    background-color: ${props => props.theme.background1};
`;

const Path = styled.div`
    height: 50px;
    overflow: hidden;
    overflow-x: auto;
    display: flex;
    align-items: center;
    gap: 6px;
    &:before,
    &:after {
        content: "";
        height: 100%;
        width: 9px;
        display: block;
        flex-shrink: 0;
    }
`;

interface Togglable {
    enabled: boolean;
}

const PathComponent = styled.div<Togglable>`
    flex-shrink: 0;
    color: ${props =>
        props.enabled ? props.theme.content0 : props.theme.content1};
    cursor: ${props => (props.enabled ? "pointer" : "default")};
    font-weight: 500;
    &:hover,
    &:active {
        text-decoration: ${props => (props.enabled ? "underline" : "none")};
        color: ${props =>
            props.enabled ? props.theme.link : props.theme.content1};
    }
`;

const Footer = styled.div`
    flex-shrink: 0;
    width: 100%;
    height: 50px;
    background-color: ${props => props.theme.background2};
    padding-left: 10px;
    padding-right: 10px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 20px;
`;

const LogoAndLink = styled.div`
    display: flex;
    align-items: center;
    flex-grow: 1;
    width: 0;
    gap: 10px;
`;

const FooterLogo = styled.div`
    height: 30px;
    flex-shrink: 0;
    & > svg {
        height: 100%;
    }
`;

const LabelledSelect = styled.div`
    display: flex;
    flex-shrink: 0;
    align-items: center;
    gap: 10px;
`;

const Label = styled.div``;

const prefersDarkTheme = window.matchMedia("(prefers-color-scheme: dark)");

function parsePathComponents() {
    if (location.hash.length < 2) {
        return [];
    }
    return location.hash
        .slice(location.hash[1] === "/" ? 2 : 1)
        .split("/")
        .filter(pathComponent => pathComponent.length > 0);
}

const loadTheme = () => {
    const themes = new Set(["auto", "light", "dark"]);
    const storedTheme = window.localStorage.getItem("theme");
    if (storedTheme && themes.has(storedTheme)) {
        return storedTheme;
    }
    return "auto";
};

const storeTheme = (selectedTheme: string) => {
    window.localStorage.setItem("theme", selectedTheme);
};

function Main() {
    // theme
    const [themeValue, setThemeValue] = React.useState(loadTheme());
    const [autoTheme, setAutoTheme] = React.useState(
        prefersDarkTheme.matches ? "dark" : "light"
    );
    let selectedTheme: DefaultTheme = theme.light;
    switch (themeValue) {
        case "auto":
            selectedTheme = autoTheme === "light" ? theme.light : theme.dark;
            break;
        case "light":
            selectedTheme = theme.light;
            break;
        case "dark":
            selectedTheme = theme.dark;
            break;
        default:
            break;
    }
    React.useEffect(() => {
        const listener = (event: MediaQueryListEvent) =>
            setAutoTheme(event.matches ? "dark" : "light");
        prefersDarkTheme.addEventListener("change", listener);
        return () => prefersDarkTheme.removeEventListener("change", listener);
    }, [themeValue]);

    // path
    const [pathComponents, setPathComponents] = React.useState(
        parsePathComponents()
    );
    React.useEffect(() => {
        const listener = () => {
            setPathComponents(parsePathComponents());
        };
        window.addEventListener("hashchange", listener);
        return () => window.removeEventListener("hashchange", listener);
    }, []);

    return (
        <ThemeProvider theme={selectedTheme}>
            <GlobalStyle />
            <StyledMain>
                <Banner>
                    <BannerLogo>
                        <Undr />
                    </BannerLogo>
                    <BannerContent>
                        <BannerTitle>
                            <BannerTitleContent>
                                Unified Neuromorphic Datasets Repository
                            </BannerTitleContent>
                        </BannerTitle>
                        <BannerTitleNarrow>
                            <BannerLogoSmall>
                                <UndrSmall />
                            </BannerLogoSmall>
                            <BannerTitleContent>
                                Unified
                                <br />
                                Neuromorphic
                                <br />
                                Datasets
                                <br />
                                Repository
                            </BannerTitleContent>
                        </BannerTitleNarrow>
                        <BannerDescription>
                            This directory provides public access to
                            Neuromorphic datasets converted into a common
                            format.
                            <br />
                            We are not the datasets&apos; authors, please cite
                            the original papers if you use them.
                        </BannerDescription>
                        <Link href="https://github.com/neuromorphicsystems/undr">
                            https://github.com/neuromorphicsystems/undr
                        </Link>
                    </BannerContent>
                </Banner>
                <Navbar>
                    <Path>
                        <PathComponent
                            enabled={pathComponents.length > 0}
                            onClick={() => {
                                if (pathComponents.length !== 0) {
                                    window.location.hash = "";
                                }
                            }}
                        >
                            UNDR/
                        </PathComponent>
                        {pathComponents.map((pathComponent, index) => (
                            <PathComponent
                                key={`${index}${pathComponent}`}
                                enabled={index < pathComponents.length - 1}
                                onClick={() => {
                                    if (index < pathComponents.length - 1) {
                                        window.location.hash = `#/${pathComponents
                                            .slice(0, index + 1)
                                            .join("/")}/`;
                                    }
                                }}
                            >
                                {`${pathComponent}/`}
                            </PathComponent>
                        ))}
                    </Path>
                </Navbar>
                <Content pathComponents={pathComponents}></Content>
                <Footer>
                    <LogoAndLink>
                        <FooterLogo>
                            <Wsu />
                        </FooterLogo>
                        <Link href="https://www.westernsydney.edu.au/icns">
                            https://www.westernsydney.edu.au/icns
                        </Link>
                    </LogoAndLink>
                    <LabelledSelect>
                        <Label>Theme</Label>
                        <Select
                            options={[
                                ["auto", "Auto"],
                                ["light", "Light"],
                                ["dark", "Dark"],
                            ]}
                            value={themeValue}
                            onChange={selectedTheme => {
                                storeTheme(selectedTheme);
                                setThemeValue(selectedTheme);
                            }}
                        />
                    </LabelledSelect>
                </Footer>
            </StyledMain>
        </ThemeProvider>
    );
}

ReactDOM.createRoot(document.getElementById("root") as HTMLElement).render(
    <Main />
);
