# Always On Top para o Omarchy

Mantém uma janela acima das outras — e mostra de relance qual é. É o
[PowerToys Always On Top](https://learn.microsoft.com/windows/powertoys/always-on-top)
portado para o [Omarchy](https://omarchy.org).

*[Read in English](README.md)*

```bash
omarchy-always-on-top          # fixa ou solta a janela em foco
omarchy-always-on-top list     # quais estão lá em cima
omarchy-always-on-top off      # solta todas
```

A janela fixada ganha uma borda na cor de destaque do seu tema, para você reconhecê-la de
relance — é o realce do PowerToys, pintado com a paleta do Omarchy.

## O que ele faz que o `hyprctl dispatch pin` não faz

- **Funciona em janela lado a lado.** O Hyprland só fixa janelas flutuantes, e responde a uma
  janela em mosaico com "Window does not qualify to be pinned". Aqui ela é solta primeiro.
- **Devolve a janela.** Ao soltar, uma janela que **nós** tornamos flutuante volta para o
  mosaico, e uma que já era flutuante fica exatamente onde estava. É essa a razão de existir
  um arquivo de estado.
- **Marca a janela**, com `active_border_color` e `border_size`, e limpa os dois de volta aos
  valores do tema quando você solta.
- **Acompanha você.** Uma janela que você fechou, ou soltou por outro caminho, é esquecida na
  próxima execução — o Hyprland reaproveita endereços, e uma entrada velha acabaria apontando
  para a janela de outra pessoa.

## Instalação

### Arch / Omarchy

```bash
sudo pacman -U omarchy-always-on-top-*-any.pkg.tar.zst   # dos Releases
```

O atalho, no `~/.config/hypr/bindings.lua`:

```lua
o.bind("SUPER + CTRL + T", "Sempre visível", "omarchy-always-on-top")
```

Para mudar o realce, no `~/.config/omarchy-always-on-top/config.json`:

```json
{ "border": 3, "colour": "#ff8800", "notify": true }
```

O `"colour"` aceita um valor hexadecimal ou qualquer cor do Hyprland (`rgba(ff880080)`);
deixando vazio, ele segue o destaque do tema. `"border": 0` desliga o realce.

### Em outras distros

`pipx install git+https://github.com/andrebbruno/omarchy-always-on-top`. Só Hyprland — é
`hyprctl` do começo ao fim.

## Comandos

```
omarchy-always-on-top            fixa ou solta a janela em foco
omarchy-always-on-top menu       o menu do Omarchy, com as outras janelas fixadas
omarchy-always-on-top list       endereços e nomes
omarchy-always-on-top off        solta todas
omarchy-always-on-top status     o realce, o que está fixado, o que nós soltamos
```

## Observações

- **Uma janela fixada acompanha você entre os workspaces.** É o que fixar significa no
  Hyprland, e normalmente é justamente o objetivo.
- **O Hyprland 0.56 renomeou as propriedades de janela para snake_case**
  (`active_border_color`, não `activeBorderColor`) e mudou os dispatchers para Lua. Os dois
  estão tratados aqui; versões mais antigas do Hyprland não são suportadas.

## Desenvolvimento

```bash
python -m pytest tests -q     # 36 testes, sem precisar de compositor
```

O que fazer com uma janela é uma função pura que devolve uma lista de comandos, e outra coisa
os executa — então os testes conferem a ordem da dança de quatro passos do fixar, que uma
janela em mosaico é solta antes, que ao desfixar a borda e o layout voltam, e que um erro
impresso na saída padrão (coisa que o `hyprctl` faz enquanto encerra com 0) ainda conta como
falha.

## Licença

MIT © Andre Bruno
