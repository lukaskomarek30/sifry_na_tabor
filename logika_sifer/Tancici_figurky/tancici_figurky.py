"""Implementace šifry Tančící figurky pro Šifrátor Mraveniště.

Modul obsahuje logiku pro šifrování, dešifrování a případnou přípravu dat
pro grafický klíč šifry. Kód je navržený tak, aby šel používat samostatně
i jako součást hlavní aplikace.
Součástí modulu je také Qt widget pro kreslené vykreslení výsledku v hlavním aplikačním rozhraní.

Základní pravidla implementace:
- vstupní text se před zpracováním normalizuje podle potřeb konkrétní šifry,
- běžné mezery, interpunkce a nepodporované symboly se zachovávají tam,
  kde to dává pro danou šifru smysl,
- veřejné funkce encrypt() a decrypt() tvoří stabilní rozhraní pro main.py,
- pomocné funkce jsou oddělené od UI vrstvy, aby se logika dala snadno testovat.
"""

import base64
import unicodedata

from PySide6.QtCore import Qt, QRectF, QTimer
from PySide6.QtGui import QColor, QFont, QPainter, QPixmap
from PySide6.QtWidgets import QWidget


GLYPH_IMAGES = {
    "A": "iVBORw0KGgoAAAANSUhEUgAAADIAAAA4CAYAAAC/pKvXAAACIUlEQVR42u2aS0sDMRDH/1m3KFilqActgl6qB/HgWUoPtqB+RD9Ii1CkFM9elCp6UfFx6qEPL0JZL1tYliabZCcxu+xAYR/ZbH6ZmWRmtmzyeIU8iIecSAFSgGQU5AlAEP4yB9KPDP4wcn1+bWoCxCfuT2bmV8N2zFWNfOXFR6oKbZnrPsISBvluAsLkqrUI6BPAXh72kd28bIjPWQWJL8U1ALdZA+HtJ6fhvbHrIEMBxCRyvEYdtnjEWtgQrGLrnGd6LoGIZreT0KZBoR3PMAQAlAC0JfvRBvINALDYvaYgRAk4/XYBtExrhDdz1wrhR5AQ0jRVteMRAPyGgzkPzz8WtHkFMJMIaQYaaYE0yFuCGS3Hrm0uaLcPYEniXUccmET/8TX94AdAmXNvRUHDjAMj8h+mopF+ghbKFmIzpuBzXJB67Hwk2fG9IaCoTNM4e0Wy3bYFTZVsFB+2DJqZsGDhCR6cEeXXLwKzDFKYmLRp+UT59UHCYEiiYMro985GtcQGyIlku07Wc/a5XJowL5MgIrMauaoR1XJphbrKQgWyQ+Dktaz5iJEVrfhiFYuUozL4D61QgNQ5+YSOtLNsWt3I8YUrIDqm0qLYHNOC9FxZwdKCNAzt1j2bIEPNLJIn35wJkhLdDNHEHwCqsX6VPmF7RBAPhlY06XqwR6SJY8NOH1CDWMv4bDg7A3BjCY5BslCn6+xnrkXFRfRbgBQgYvkDtBtmbv3OOwUAAAAASUVORK5CYII=",
    "B": "iVBORw0KGgoAAAANSUhEUgAAADIAAAA8CAYAAAAkNenBAAAB70lEQVR42u2aPUsDQRCG35UQEiwiGBAJCLESUlgZsbFS8Df6TyQ2IoJnZRURCxVEECEEFGJsxuaEcOSye7Oft+zAFWFzwzz7zuzO3p34ejhHDLaGSCyBJBAPILRw+bZnWTx1UaTPVYRiSS0Ra7F/eo6TdEAWVelWTDeSXO8aEIKjiFji9F4BQGbbADKGMpOygYbCzaIQ3D6AGYC2ZrocrhibAWgBGKvWrWqNXBZ+tyyubJT7B4CB6uKjCnJaIX8fFRReFti8ZHKUVtAqG6JQrIu9kmA/Snz839902WsJBaDXkvGtiguDsAmiArSTBzhj9m9PnA25oVmYAsAUQGfJWIvpz1sbvwHgwsCECJc1UmZnzECuTPV1DZg1UaF7NtqY2jqP3LiEsAlyIBnP6gIi29yG6eFDgCBvsYD0QgeZx5JaTR/p5bvYe7GABJtaU0ZTmIUI0mG0Jrt1SS1ZX9Wta42IOtQIN2gKCYR8qhLS8kuhgshm/ToWRY5DBCmmxYvr9LKlSN910adey+AsF///7QuEDMOvh6DITyyp1Tbkh+pc7Lc+FSGDS+mRjipckBHcfOZBNkEyACcO+zNacYTWAhm6OiwVjtBkGmRsOeg7zkbLARnkTieW1Fj8IuIXiq/ldN5YbYZ0rk9NYwJJIKvtD2+hXIAmcPRDAAAAAElFTkSuQmCC",
    "C": "iVBORw0KGgoAAAANSUhEUgAAADIAAAA4CAYAAAC/pKvXAAAB+UlEQVR42u2av0sDMRTHvznLjS4qUiyidHASBKHWwerg4N/ofyKC1DpoRZAOokOhFbQIioN1qShx6XCEM5cfL3e5mgcHTe/daz55P5LXlo3vjzELEmFGJIAEkJKBfADgKdejK5AKsT2ecX81ocN89QgPOeIZiGqonFGHlYscSU6wDWDfANS70DoIORJAzOTuj02PAxgJus8S3W8ANwA6eSW7zj5RFfRrEhtzALYl9xmlR04tPd93vdGqghxagtQTq/vlS44wANcAbqev2TQHholxmrwA+AQQJ/RkV0/HKxVD1+4I45qCnWXNBdvSycvIwBulLL+uTrTcYOE6VB5R9UbfEfxe3jt7ndjem21ouW6UVO0vqTwTlT3Js0AGhvYuc5hzWwdkTRhPFD+k6SC8RJ1NHZArYRxbdo2MMDwXdEB2Afw4yJFxyntd1z27bj//pFAk5lNCpUFRaCj3kZX/1uqysoHoTHhQRo8AwEVGufcGZJhxv+VraIk7+rqBjYkPIE2CHIp9C62exbOvRYJ0U3ptU68sFgnSgAdCHVonBLky8gHkiMBGtQiQCdECsKJDK3Z0huJ5glB/OcFs7EdEEO+OihF3CcJV20+iXOEAHqhBivpTwIZNqytbMS45khfS10QExluOJn6uUwkrrlcqL9vh5+kAEkDk8guPQ13G0PGqVQAAAABJRU5ErkJggg==",
    "D": "iVBORw0KGgoAAAANSUhEUgAAADAAAAA7CAYAAAA9xQlEAAACDElEQVR42u1aPUsDQRB9ewlB8CNFCBZaKATSCPko1EIUxF/pPxEVRNOYIiZYmMKgjYUQgpiAWsjaXHEciTezN3d7G27g4FhmZ+ftzNvZuURNn87hsnhwXHIAOYCEANwA0P5jU3SUH4sAnISM2JDOHDBWUqhnOO+IolQk6CjmwkMA9Yjdo9pUURlAicA1cbEXf7E6MbcpcilxCp0SF9thRGlK1DsLvA84AMIh7gvzYsNgTtOUAwDQYHBFC/GJRH5PkLzBeQrAb2Ds28Bei+IL5xjl1oOg7RVbVwkVw7ZCClJk6uuQYx0Ah366fAEYA/gBsMWI4LsfoTUABe5GUAuZjnCkAKAEoGywiZvLfBsdSwG4s+C4AlCV4sCx0MkUlgmASpokphJMG87LOzKpLmrpe+Ke6wBaOQcSAvDpOoB1hm7f9RRq5BxICYAKPOI1QxKAttHUpJ1C8wANswrgjahXzyqA7QXjgyymEIeMzTljj1mLAJe8e67VgaVsaO5tAfgw3N2w3r4tAGWbYZNOoVFMLsxsA6jFnL+aNoBbAdAPNlPoIPDeNbTRjnNDjQugtAAMVyY2IiD5/adi2m56Qs5fCYDohtrNZ9IxZvCHpyQbF7ZtT2CBMZIV/d81Q6IOVAWdHRFOu1gAVMJ9bo27nmkElF+AkgDzCuCCajvODxzthKKw62o/4HxDkwNwUv4AitxSa//LhjoAAAAASUVORK5CYII=",
    "E": "iVBORw0KGgoAAAANSUhEUgAAADEAAAA8CAYAAADPAlLCAAACK0lEQVR42u2aS0vDQBDH/2lzKRYVrIiPg1BQD4rSgw+QevGgX9EPUhAvgojag6UoPrDiRVRQBKlCBdt4sbAuabO7mX2kZE5ttruZ38zO7ExSr3m9h6RLBgMgKUQKYRCiASBwHcLvMxZwn72keaIzCNuJt/q+5LqHf94LGI8+mIZ45r7vCK7XVXorZGyWGb8wATFFtL7XI5YWKROGL2FhlcDuKlq3lWKPFS0fJssSvyWF2CTeQqLjWk/sl5heIVdeFIK96URaO2ksX3zDinTnVwF8AyibgvA0WHG1j1HassZ1sRTPcuUKGUTTElCHEmKYSZFVAEcSirRili3kgQ0AaxLBfw+gqKAYu8YjgBmbMVEk8MC0i4HdUJjzahLik9A7rDcKJiGGNHrwJknnRC+ZNwHxpEFxoRRLCTFpq4g0vZ3eYvYUH1SHXZgc9Lh+CyDPHFZsTaQCM6ITYjvk2h2AhYjcP+56UzQXMV4QXKcW1d76BuNBtScpmfBEoJoak9hje7r67owhZZ32hKwlW0nYTlFK5kKuVVyDyCnM2bUJwW+ld1sxQ+mJMVs1OhVELWYhV7EB8SN7qnIyShkXqhBZl1o+iu10qTjv1CWIJcV5G6IPAnRABITpsi7yIIAagvoR/wrF+qIQZ9D3pucrBOREZgHfgvV5yYfcYx3AuWjqjhPYukvuEuV28iD3PsJ4TyLqiTLXqF9pULoNxXfdvkPbSPmhRfpHxhQihfgvv4/PWv3lS9LWAAAAAElFTkSuQmCC",
    "F": "iVBORw0KGgoAAAANSUhEUgAAADAAAAA8CAYAAAAgwDn8AAAB30lEQVR42u1ZS0vEMBCehCIeREXx5MmrrHgQhAVZvSz4G/0nix5UBBE8rCwiePLgUYq6iPYg42UDpYQmTWfyqB0ItE0zyZd882rF/OkMUhYJiUsPoAfQcQBYakXqJ7CUGoDbkBRCTXttqGMIALlvAGqxOtk29Otk0yeAJgu7cdCfx2QDRw6b8swN4MXyvR9H/UPdw4wQwI6BUiK1QCZaLr6wGc8JAB0NvDZw9bmQRqYA8KkJXDbBra4pmdRNnjlSwqecUpxAqMW/+baBByLvpdqW6eWMcPeVq5sBwMBCpwxhxB+VHSo3JXs+vZ9J0axyv56aGx046MSYAHDlMugDAEICIgPsvhcAhaO+d980khaZYN5A31qMFNroejYa1BtlHhYpOD2bNCRUbT2QCE0hQUwHQU2jvqRcyHmD09PVDNfOHCX6yYcN6YdU9sJFobmh/yL2OLBq6B9rnj2GAnBPBHo3FIADRy6LmCnkKpepAaiewrFvAN+hC5+2AJYJ1jCJxQauHMdVv31OQwE4aTH2q3S97wsAZW6/Urm/4wbA8f/rt3R9aLtBMvDOm6pDpAaAnIlZzZzIacTjlAoawRyshMY1186ZtZgImcCIRYU24najnCcx4qJQZ4v6HsC/BfAH5nBjQk+BK5oAAAAASUVORK5CYII=",
    "G": "iVBORw0KGgoAAAANSUhEUgAAADIAAAA3CAYAAABO8hkCAAACHklEQVR42u2YTUsDMRCG32yLrQhWRASleNGDFxG8iQcVFD9+oj+kVOxBQaFeigeLiJ5E6UEEpYKlFOIlQll2t/mYSbvrDuyh2TSZZ+edZBLRfThDFixARiwHyUFSBiJjnus0gFwMORxnOxp9xg5y8B9zREwyiBgXBEdEhHp6Ce9SJa1pTqfzfcTSPrMA0gZQidkkWazItKuPev8FYG6SI6L7xSvU0aECaVk6Ria3oscojBqjD6A0jojcEctjymW8wOELbka0P2lshI0RfSSAb25pvQNYcKyh9kP9o6Iwo9oFR0QGMRBXhuVIYFCDSQCXVCBtNWAh1N5UDuwRVclxQLtq/rqttAYRzrOW4kNj1wCchNqPkuQWJIS0YFmK1whgTtU89xHv6i45opsHMuJLxvW71ei3ETHvYmQYY65MpYWUpIOUTMYWthFpMpcZ0qDkF6bJLgC8qpPeNnN5MlxECtuoJa1aVQKAG7X6VQGsGkjIeFUsWkrBVfc6ZxYjmMAQQGrcoAhN0AZl7rmeR0ycD9shkq+P/uyZG+SFcDdPuj5aowbphH6vMJQnHR/nkWUPtzpLod+PvnJEMoOtc4F4vQYdxy0Khf24fDQbkD6TvMq+I1LyEJ23NEtLt84jBRHE8pJZSnanldEFpJeV5bfM5JME8OELRDLLad50joAIossYHRaQVkz7LIHT5y5/Nj3qbjHm63HWlt8cJAeZJPsFlAZuLkUpKrkAAAAASUVORK5CYII=",
    "H": "iVBORw0KGgoAAAANSUhEUgAAAC8AAAA6CAYAAAAgPACEAAACHElEQVR42u1YwUoDMRCdWQoe6kGKPdmbBy+VXgQtaHvUb/RHrKAgFXERBEHRg3rTWyuI9dJLvOzCsmySSTLZzdodWCibNPN28uZlJvjzcgp1tQhqbP8S/CIAbCJ5SOCnmT+0Awqw9COy4I8CY8V1nTk/MgH/W7BdVdMltScd+HXNAjp7zPAz/7gABwDYpdAGLT7gKpnTd1EOhb8v2cRWwTssWEBIPgwAYOyJKqDwqUxYdKSQqT3YrK9SG5RQJG93RF/nkvdvADAg+tfSRkWhcQGF9jO/PwBgq0CvR0SakIFTdf7eIAF7BOBTTQIjB21S21MsqFOR7Kk9SebKTvJXE+AU2uhUKL/975aJjjZZbloeIADMFOPbFhjQVqJsapuui0Mu4K6FmYvjGUcAIobIxRb/6YbSBg4NoshFt6YBb8CHAP7GcbxS8Iea8Z0602YzZPCirpw36U9vQwFvcztwwLVLUYU0Ecl1Sang54z87rusFVlEq0OYd5bUMUisZ0Ryg2BkLUaKoGZsAgDHijkDH5FXAb8wiO4JYW4qAAvOyOcdcPQBqsC0fSUs58FG3TU2IGWcpGyXTgiB2krW85zUEbY7HXFycNVps/QF/rsE1VnzBX7DA1hRJm0+q9Z2F/C9qlu/EBM2rgI8l4RatYYm4C890GTp0hNTS+I5sYOykUYhUSHkinzHI2XiAjV75oy8z/Jg2FSVDfgGPM3+ADRPcoi+jD8BAAAAAElFTkSuQmCC",
    "I": "iVBORw0KGgoAAAANSUhEUgAAADIAAAA2CAYAAACFrsqnAAACEklEQVR42u2au0oDQRSG/1lDLEwasbIKCEGs1EYLBSGI7+iDiIIGFES0iKYQhSi2ETtNwITIsdnAMOxl7jtZ9sCQ7O7s7nxzzn/mkrCfl1OUwSKUxCqQCmTBQJ4AkFB6LkFqlp9HGdd2uOssZI+QQt3Xsmhkswwgv6FrhI/7EYAZgD8Aqyl1ghb73BoJumEu3ewytMhnvPrUyHeoIGcJgx5fRGvm1J8AeAZw7lIjHwBajj1WB7AVF8pIJEYeaSFwkwGZBNDOng2QunD8nlDn09VAx83TjDQixmoXQMdC2pUdU8hmaPHWkahzXcS4pAIi24tHjqY92h4hhGdvqiBXuj0T29hi6F1w3zdSXZeyr0WGIFkenQJYNngW09UI03gp5aRz1bCd5nVQZJotOLtXbCABuJGsV/e1HtFNDIfxvcZrlchCFiFLHSE7ze+rgLC4PGT0FmVlEQ1rpnTKvC2X8ee2jkf2NMTMp00mlK6kd0YJ5499rdkJwBDAusQUJ68jVlS1U7MkaFWxMkkgaRhTsTPDjDO//3GRNh+ybNc0BauADAoAZC5A2gnnZr7WG65Da8kiSN8niMttz6FwfOtb7HeWQE6E4wPfIPshpD0dEOahXcy32G1lr6+iBsSB5ey1ZupxXZB2aNsrIf5hgHyCUGgwkaWXjB1kKXIJkvYTQ6Noz6iuEJcdhhMrm9grkAokJPsHWftzbHZ6VVUAAAAASUVORK5CYII=",
    "J": "iVBORw0KGgoAAAANSUhEUgAAADEAAAA5CAYAAACfz8NxAAAB4ElEQVR42u2YwUoDMRBAZ9JF9Kq9KfXgQenFi2cVpOA3+iNSKGLxXOhF9CBIRU9SETyoUFgvKcRl250kM8nukoGl3ZJM5k1mkpni18MVNF0UtEASRIIIAJEbz3tkG01bZq470Y0MYEqvieGElEEZl6IKD/rowwp9JAgu44tjUDqxh5aG2YzzcQzaQFy28Z7IGXNnbDH22zex0SFElsY9AsAhwwGxSZmvmJN2KUcMiXvPFU4YwogV0qfaoRxOil/9udAlyRwAPvVvU6NM6ZfMvTVKCBPWLC0WtmFMvexMpRv6s1NSkhxXhN4ZITw7baxikQsC60ypLD1S9owA4MVh7R89f7xGN4YKpwEA7BuLTogO2dLfz+vY2Z2k9jRBJIh2QgxDQmQCOsvKcNEWlRMid5yDdQinZ8/+Ovftz7MI3mffFRUAwKYOcvrbVAls//UawykwXYmmiOp9m1BAgj7yCZZ5AvieLFQYlMoJ7u5tlaEfTSs7ykB2uDs7aXl1OQHrthO7LvbZQtwJXnbByo7TtpbiXLsxL7zfSEJIJfh24f0idXYO8hTgvmCHKC5y4Gn0LNZOjBg934sFMWCEeIsB4d1SFmTPR79rUxRKRGqnXPDucNaRhVpIUn+67BJEgvgvf8IlYb5t3679AAAAAElFTkSuQmCC",
    "K": "iVBORw0KGgoAAAANSUhEUgAAADMAAAA6CAYAAAAdrmHiAAACM0lEQVR42u2az0vDMBTHv+mGP0DYYdvFiw5xHjzoVBRv/p3+N95E/LWDKExhCrLD5hBUHDKNlw5KSdokTV67kgeFdkte+0m+fXl5G/u4P0VZLECJzMN4mALAXM8TTFXyOY+dMy+zAsL0ywTTMvD7HcpTdpDCXEXOhxr+huHDLqW04wAeqWAOIucNDX86bd8oZfYriW46xgE8Sb47ooSpGvgbxK4ZgA1BO5ZXAJjZVKHNavigDMCPBIJRBwDRCOrO1CJ1WA809a/77qwXDYYJoKYJa8dteP2dMCDvlLlZmlVS8jmkrDU1jVnuAWjblNlZjlnKpiq4KswJgG6ZsubdSGiVHX0AI0fPym3CqFgLQBPAi2JgUTly38+s+c2Z2M5VpTYPMMdl2zZH352/MtQAvtIy7sDxaA4AvFrytxJLmaylM5nXBGQrYe1QzIxuZs0VawxKfm3BfGbYWjfCvpcaffquZGardLSfID0Wuc8EkvJX4FhSXYP0hENc4571X7YtM64gAxYmpyZ1gI7JBq5qGUInOrEUnzXdiGcjABhluIL+44QBvKOAubAY1usJUNsUMIcOFtxnqi3AmCAH65jeMzCQArXVKQMAR0HMBMbl75vxwuHINYxLi/9m06SAmcSuHyzBNKllBkF+tGUJZiGLnIskM55HAJCNnM2oxqhhCjdL/l9NktHLuv5MBP6nFDAuVn3RDrKicy9TmJ4jpdxk6Wxa0Gg7gtnL650pVQDwMB5G0f4BJHZxT8AvkJsAAAAASUVORK5CYII=",
    "L": "iVBORw0KGgoAAAANSUhEUgAAADMAAAA6CAYAAAAdrmHiAAACA0lEQVR42u1ZPUsDMRh+oqXWpYObtCCl0Aq6dLIu0kHw4yf6Q/zASRwqHboIaqlDETupUwcVhbjcQYg98p02IQ8cd0eO3D15nzx53xyZPZ4hFqwgIiQyiUwi8w80O4InQwuuk8x0MQTwJpKIBIjogZIHSRS1TQHUYzGAmmGkojEAEjKZ4SIjQyQm7EBmUmfoyBhByfGIEgBPANoqrqRgJt5l1rbY1yBkA+CjsudjnfkGULYtGw5jmzLLV/AP5jo/yh6i1LJFhh3NjVQCqOE9O99K2rz0nOkL2m8A9DTmBVlEZLrM9RUzUvnRC1VmxyHXM6xcRjEVZ9shk/k0mKwvgvaRbzIVg363BO3VkNYZkTVv+iRDDfIpqvCcl7JZZ0F71vw4ukwyy0k0HcrSmAyRzI2aFucZdRmZA4OXj+ekPjLyvfcpsyISBMCE+eiWYLNjVtC+qxslHTIEwAOArzmG0VDopyoRLQrJbSYTA9gBsG7RVXNSF3PaOj7cjKoUTpI4NVkmdMlcxlA297OIHGX3ryGT2efua45zOuKSTDTFWdFonVv6lt9lyM1OLJFZNU120w9aONjzstG/rchcO65MvZI5DFlmNsFv/975JsPLYmJAhl+Iu77rGR4Ny9GiPshQR1Kb2niX6m9AV5ZcZ7LxCoAfAGuuybiG0V+GlAEkMomMGv4AGgRepN35YecAAAAASUVORK5CYII=",
    "M": "iVBORw0KGgoAAAANSUhEUgAAADMAAAA5CAYAAACbOhNMAAACIklEQVR42u2ZP0tDMRDAL89qC0odHIqtiINSsBR10Q7awc2v6FcRF0WqoqL4XxDsoHQSpIpSaeOSwiMkecnLe69JTKBDLndpfrlL7tKi7v0uuNICcKh5GA+TQculNC+OGEc2eAZLgAz12ibDYEX9cZNh3hX1yybDzABAT0KvZ8uZyZOFIgDoU2MfRJ638WrOAcBLqD9te55Z8EnTQBjMkQ1sgmlH5BxExk9ML2dUEuc60UcmegZr2LVNgcEaIMM2n8Ac2jBxF9BLeD5tmBZD9iV5BiaI3k2Sng40wqpBya8AYIpj0+fI60lCBQmcjS5Z0CrpPzB0xhiyDgOK9737ScGIdugcAIqUrMrR/aH6JU4OYkFtkzV8x80zST99Cwq6iLOGgig38Twz4MT9sWD3RO0xiw3jeeYNACoUiE61UNWwRbIXAc8zlZhlz0FKNeSdDkzceqkpmA8p5Cu61QiQMMSDCPeqno+niI1h5ZOG5Ny1rJ8ASxHjdVseZ2catnumwZQlzx5L9msazKyG7Y7pvwE8KybDy1DpFP60qLIKA8B1mjAXDNlihM0p1V/h6DUYSbOeJsxaDJsNBd3uKMNMNje9CuyPQnmumBXMrYbtHJWcw0l6U2DXSQtmmeofpuBpLPEWSiXMmjCi5v+gFcQuGuWFouuZkkme8X9pcF6VyGaYLVc8g10LM6NCLC4MduUC+HTpNpt0qQJALnkGPIyH+ecwf8VqaHGlCB8lAAAAAElFTkSuQmCC",
    "N": "iVBORw0KGgoAAAANSUhEUgAAADUAAAA/CAYAAABAfYAWAAACXUlEQVR42u2aTUsDMRCG39hFEQSVIrQV6kEPgoJ68uipiP5Ef4gf6EHxVkW8iAiKH4ilUEqLCiqV9eAuhJBuJ002zYYdWEw2aZhnZzIz2ZW93+7BNxmDh5JD5VAOQ4XR5YrccDqFqlCuwcSyIvQ/fHS/jgpUi2szh6FaKlAXXPvVIYhTob+uArXLtecBHA6pxL6wsXX2aghgC8AvgHqSBwXEBbejRamu+AagPEBBFffm5xcAbCZNToJikqdKATMdNcX16rp5illQWgWoMchK1JCuCtYiKvyZYHXZ3jsBUDFZJjEAbWKCnovmMwDNPmsxAFMKSf8IQI1q3kDBFYp9rBT3XwAsCGMlosu+RlGW6inGoJICCABUuftsyD2jDaRTJlEiYAjgWTJ2RchXZzqVTKARmRjhaVcl4xtpWMd0QcsAdA2tY6TONFWlz2go9GO6aA5gVmLlvgGMG9ibTh3nJ0Z5ZMlfvAwhTR+hSpYreitQl6OwVJDi2lQrXPc7lmc5UKxlxf32fYx+Oz6HdKp0sgqVVLBOZ91SLIvu90iYc5dmIk4DalZy70DoL2fNUrL9sSu5d+Jj9KtlGYoNGPsS9tUb5B8V4qsT/e25nKcmoyN9LGWiexdsQfWGCN8h8egvk2MbUIWU8tYTl7zPbR49xDzTVgSLf9/F/9spineVbJ+niilYTHxwqy4XtE6GdPFjd2OUUKbcT/wMU0lJX2bTUl66n9WjhQ2oex8ttci1H3yAEt8tLPkANQ0HRQfKxf8H1IJyFsh0SGdZh2Lc1XDNUibKpIrP7pdD5VA5FPAH3SJz3Vj36FkAAAAASUVORK5CYII=",
    "O": "iVBORw0KGgoAAAANSUhEUgAAADIAAAA6CAYAAADybArcAAABz0lEQVR42u2ZPUvEQBCG3wnBE2wsFCxEsbAT1MqzUUt/oz9Er1SuUAQlYiFYaSEoKAgK4jVjEyEs2WST2+/bhYULm2T2ybyzM7tHXw8niKFliKQlkAQSGAjX9HOTILkBAFk7rIyTzx6RQdRNehRLjByHCCJ66tr3YKeyX7SM74UQ7ABwVOMNMu12k9IqFFcz70G2Q06IBYAPiQfEBPnoMkZ+AMxrsr2pIDkyAcKw31gVJvMYIrrql3WBXArXV5XkJuuqyXOad3QGGQrX+w5k+K1bWmRRUlVbC9OCMAJpXTxyptHuqeJ9N6oflRrOtX4BzHWUFRuQKas80+SRKsRbqNK6Fa5XDNi+7/HMZ1eQXQsfcavHM4s2SpSmeyaKybbtndwVZKx5+zuQBOrQdIwcCIbJUQz/271rK11yxRfpnBj3hHFW/ZLG+LMG4ryUyRzqvvqby0qibm8vdqsgpDjOQiXRe5lP/480fKGJxvk9uVy1Bj3kN5ZsdzdUjeaOFUG+SIstbIXZlbSctDyAOb4DWCoD/xXAum6QZwuyAoBl09Jaiy2PAMBLLCCroYJ4d3A307WWjSRoHIRj8EgRi7R2LBxOWCtRKKZgTyAJZJZA/gAb8VjgCP4BGQAAAABJRU5ErkJggg==",
    "P": "iVBORw0KGgoAAAANSUhEUgAAADEAAAA9CAYAAAAEXoFnAAAB9UlEQVR42u2YzUrDQBCAZ6tYRaiCeLEnQdFbi/bivUKf0Tcp9eZBBdH2pPXUg8VLEaWCUsTtJYV1MZudyW4ySXcgkNBtMt/O746YPl5A0aUCJZAAESAygJAMdOtFesgkfXSIvvKHvEHaVEs0GHvNCyUmBOFD0nBhpas9130Hto2iWJgOAIxtNlWH+CYC+JI6JSY2mGWohUywKXaG/IBArMPE2Zdyv4uFqBKsIZTrJqXyC1l3WbGxbnXm2JW6VAjhUIleymTRSWOJV0dB3vYd9SaIPUQhSypscev60e/XMbXEyiNWc06dDRe9WlJgv+UEN8DEZRLEjmdlr5QuYaCk4ybmJTbuJAgZJU6mAFDjfLKzga35MGfWx9O7MkCccod4L8O0Y6sMELBMELdcITBZp8kVooVYu8YVQhoONGPfwwWfXazIaujgwhL3xJZEcoI4sVR6VIYUu88ZIvchW8VzQJuGDzbn8B/l/tcXBLbp+2/48Gmw5orN5qSF0Ju+S8I7Nrm507nD4+7Mdi2HLnYCAB/R0ECd6VazqNiSuMPYtXqj2SraeULfqAOf7jTMCGrbJ8SxR8WHAPBgckFqTDw58G9nsUO1xNGyn7EDhCsIWXSIZ0dFK1eIw6K7kyx6TEiH/Q+LwB5xs4RtxRbAWEKxCxAB4q/MATHIbydajzfhAAAAAElFTkSuQmCC",
    "Q": "iVBORw0KGgoAAAANSUhEUgAAADQAAAA7CAYAAAA0Lqk+AAACJUlEQVR42u2Yz0sCQRTH35gQUllUJ4MozOpghB46SlAQ+Cf2jxgEIRREhzaioEIDA6FLQWWHJYLpMsI0zK5v3ZmdmXUfLLo6+5yP830/Zsjg4RjSZDlImWVAGZBlQJRdzgOJIC9pk9xS2oBmx/RPQ66uKSAS0ecvMvbKOuIzh4D4iuhzynbJzWn8/ackgV6FWMDaGWLMJ1PBdpJAJeEeK70DNlkiib8e+2zBlOR8BdK75d6vmY6hgiQNR7Vd25LCuXB/FzDuFAAeJfVGVpsudQER5AZPVz9HhD+qCgAdANh0tdvme8Qqe60EdBZ9lUBEE9Aqm6yHGLuieoUIi6cBAPwoBqsjx3mqJdcAgCIATAu1RnZdI5INX6uC/LS4Z2omY+gN8edgrGlLUjjUlDk9U0DDrrujOL3XTKftio071qiG3Y1+j7lKXtJAZeS4mTH912ztFJyQ3LumuVJMltQBtBhzoljzTUuOKO4JCyaBeJAbyfcnEX0Qm5JCnTW4vB2pWuWc5sAF+H96NLSia4WVtxJy3JUrQEHWE+73XAAK0/t6iGQ/IPygnyYBRBU90wWAeVcPSS5i9IHtpIEwRbSB9CNL13mdQDQmuM/ODmRnCkFbhi2Zs7ym1blX0caM2DIsJym5HZe3D6IUnk1mGRWSE6WwYTDJZDvWUdZyHUhM1820rZDTkqMxa49VQNSm2hMXiKZJcm3bYyhqYd2ftDqUAWVAkwb0B9KlbTy6DvfbAAAAAElFTkSuQmCC",
    "R": "iVBORw0KGgoAAAANSUhEUgAAADMAAAA7CAYAAADW8rJHAAAB3UlEQVR42u2Zy0oDMRSG/5QqlYJVdGV9AxeiLhTEy3P6JC1uqiKCCLrSF+i48QKlFS+b42ZGhpBxZjI5mSSdA6FDmFy+/ueStGL6dIZQrIWArIFpYBqYP7sDQHG79B1mL/V8lPVSm3kTAwCrABYA7HITc8FQTt8XgKUS84mMOVlhqOB7HdcTwDOjB40lldhhNhhh+nXEjCjgcsLHOiMMgVDR8c0JwKKlVZlyw5xLC8stbRPF+Le4EYCZNEYev2wyAVDF2tLLebdbcj5tZciHmGk7vj9hWhlSLJC0KCMWym44q1nNZpsAVjQ2cq274SowY03Z82LssI4604dH1uIKRtdgiBmEbMGMQjqbnVRQhXyIGbjuai2mBUXRHyF8OM5QCG5GOUqp7JMbJln80UBaFjnJpGNLma15vTarXOyi4EmCXIwZ2U4z+t99qzP/xdqaou8bwI3UN/D1prkI4EDhclT0izKlzIvGmCvTJcAUzLrGmGNfYqZKbYoADBXX8HvXY6YM9I4NZUYWbqRky82Su8+kZpWNxkwvPstx2C2AHwCvAD7iT+MxQ5bOcvs+3DSdcbNZSDBdC1nMCsxDSG627ZoqujAUSgJw+h80E6k5cgWmbNEUoSvTwDQw8wTzC+BIUpbrJyPvAAAAAElFTkSuQmCC",
    "S": "iVBORw0KGgoAAAANSUhEUgAAADMAAAA4CAYAAABQZsDpAAAB1klEQVR42u2ZsUoDQRCGZ47DRjAQ1CJKiGAhVhYWsbL1GX2TdGKjFoI2ioVowJBCA0IEtVobD47jNre7szO3u9zAQcIdu3zz784/e4fLx3NIJTJIKDqYDiYBGFVzXXBNljNC6OK0dB9jXGbPDtDBwuz7VkFymWEl80oiYznz+FgDw6aQdGl+iN1nrkq/D2OHGadgmneaja9iKwDK4D6GrsylReaVb5V8KfMGADsEFTEUZRQBpDzGS5swn5plgo6ZHlGXXUbIZG+F408tuoO6sacSMN+Gagwt2p06qKGLSrmlGjYZtu3hFLU4ZIYQPvdGEb+G4xmX8MzRB5BgmEWsrRj72gUqc1gO7IcsADj5n2eugfqiwnBA3DTcH2gSuE6BefLUk1VjW6o3KzIyAYADYqVCAFhqjFK0NzvzNNcG0eGRooyPtl+iWLT2DgAbjtXBwpiqMg4NxmYv3LZxbObarMdc7wFC+aTxHirMvcEzk8r/TUkYLF2zhmePBL2LrMxuBa64Xom+suCCWTgUgz1ikehzwfSFNv5cYpkVWZsBwA8jzEDKZ0T7Kpczf6g+k4xpYkow3tqoUGAwVWWc1Qm5AKiYYT6oQCHBbHGaZnSFoDPNDqaDsYs/tZhXayHwVGIAAAAASUVORK5CYII=",
    "T": "iVBORw0KGgoAAAANSUhEUgAAADQAAAA+CAYAAABk4ziNAAACA0lEQVR42u2ZPUvEQBCG3z2DxEqxVFEsRLHRTgSLKxT1L/pDRNHmClFs9Arxo/EDxcpCLE5BWZssHCGb/ZrcbpYdSHHZZLNP5p3ZmRz7uj1ATNZBZJaAElACqjVeHFLLFDcLYwGCVa5L5qGbQD30biu51UCBZmyBWI38WpsUylC/FvMPhgJZHNcEsQMAPZssNww1ZuApsfi8YmytGHt1gAGALlXappLfrMMzmcs+xABcNgSlmufRBEa1Dw3bRsXEHMAngCnJS+CaL8sElrkkBZ3JJosHH0qur7rntGbMCcYmhmQL2S8WcaSxkB1FIinD9E0qlcxS+zJJ7RbnmWaccAdJkhendbIRb/pOsTeRwlBV2wzAi2RsueJcrpjvwqUYzkBjCwTp/BvAhOtCqIDKMuEW9wTd4Oks8q+JPiuDH2usYfTVgv+0DUgVQ+PpI0kCGp3chH3E5qHpJDkPQCexAW17+j4xUsmJNuMstrS91TYgne8ALCYPtb5S0PXGc4hADwbXPpV+z/vsh2RxsmTgnUU0+G9GxxGGai85DzmGji3ia9MHENMM9L22ZTkmOXqG+0y/iRKIUnJdw+vXm6jr0sZKbL3YgLrUsgtBcm+xFadzlFV4iEmBxwYUZdrmMXpo0Hag+9Lv3MZTIQGtxBhDosi9MqjunTpWH9VDStsJKAGN0P4BAt5dRRQoMEgAAAAASUVORK5CYII=",
    "U": "iVBORw0KGgoAAAANSUhEUgAAADIAAAA6CAYAAADybArcAAACTklEQVR42u2aSUsDMRTH/ymiCNKKVASFouDJhYp6EISCC+hn9IO4IB7Ugx7UKm4oFK0oCEW0iFJFiJcpDCGzJPMyzQzzIJCk00l+yVvy0rLP2w2kQXJIiWQgGUgCQR4ANJw6F0o9CSAHzmRHARSduiglj36rQGY8+i8kfdxmkHuP/rKPCloJMg/gRuH5O4pBuwwZ+mSA+vwC6KEc0BSIW5gAw7I40mGQZ5tB9pyg9icJdmIZkbhcd7mM20a4ocWckrxb2RnkYjJ2VelWXbg4QM4ieCoeFiinoVYcFkoYkE3Jd1iI0pZvH5XzKy3Xs28UIEsaC/Thqi9qLnKva0EGKECaGoZbkPS1JC5cRaU/orrfIYKjhcyuVhTfUYiyIzpGTvmcuHjbFO73q0MOqeqqr+mAiAlPX4dAZoX2tSrIqMagdUMwbhWbUAX51NDpko0BMU80Rg3ADoAXyWc/VI7BdIbIAYz7TKg7rlSXKU46aMcZwVmN2ZrqnoScPPNbWCqQ3Qi7OWdTzr4qtK+IEy1tkIOAPLzuOl7LdP5d4w7AiLEHucWgS+iK4jyWTe3IcMjvP4U4rocJtsZUa1Jonzq6vQNgH8CW0/8K4FiSEAVJnhrES7XOPTzLus/zZahdSDeFHKMBYJAapKz4nhmNsfudHW0nbsW43O8l6GXItI3UJH3TBkD2qdwws+CfD5wiYNpw1nq06YgSRcaE9lFSQURZSAsIkgxyqHE/YCVIRTPhSoRqzaXJRniajJ0nDUT2Y081bKS3fUdmsziSgWQgNPIPbOh+wH9E+ioAAAAASUVORK5CYII=",
    "V": "iVBORw0KGgoAAAANSUhEUgAAADMAAAA8CAYAAADL94L/AAACHklEQVR42u2YS0sDMRCAJ6XowYJSLIJ6qEXx4KW3HlRQUfA3+lfUg4UerCcRFQTRQ1WEFnyCPWi87MIQ0t1k814ysGyy2d3kS2YmMyGft0dQFqlAiSTCRBjHMAMAoOjyQT6yGqsZbUueTTxFdyKzMiPPQAZMvSsDM2bqpMAArhk1VVHZZea7ioyaLSraCRVsJ5L2nX7XsuXNxhqhIWOypWBIQRu6MOwACnkzLHWJTrckBtAX/OeXiP3mqdkLKh8XmE1ex7/JcwIAHcH/zOiIALBu7mtQlVcJbeCt7qVP4cyC5PunTL2tCvOo4H3OFeH3ZF4WWfIVBkI1Tiv6PVG1mVKmAMTxOIlOGEDuNOvSJd+ofO8qOUuhegIuOmtSaqi86jrTXM9pr4WUNs/r2NHjGYBmuULl9+TeYzbfYGCeUHkuuW8CQDMnVPES5jDxQnkp8q7ujqsGYO4A4Flg3yEhwKwlV/AOwOlhoU6Ybk5UYBxeJ8w259mJzWDV9KZ5EPqmmcpNTtbqLcwf59nGhKzVexgVe6A2YNjD7jEqjyD7IJy4yForEm52CpXr4KFMgmkZVjn2MO/BJEyDqQ81T2KbqTdNwkxz4Hi5ej85cPgpAG0t0GSN+g3lJlg6IdgMK7MWxkJtwQQhVdt7AacfalvNbAmNauYRDCmrmimpmi8wwzKtTEPH6vjsAGiZYKSBfII5MxUBuJCdGJtFmAhjV/4BEcFiYfvZmfgAAAAASUVORK5CYII=",
    "W": "iVBORw0KGgoAAAANSUhEUgAAADEAAAA8CAYAAADPAlLCAAAB/ElEQVR42u1ZTUsDMRCdWQseRBRBPEsLBT1oQbxZe7O/0V+i4KF6q2jBgx8HS8Gbh6JVQRBtvOxCCOluNplkkyUDgYV2J3l5k5k3Wfx8PIXQLYEaWAQRQTgAwbjxVAcm2iGCYNzzDADQwD/PqFMQ59zzOuHCrQGSgehzz78aACj/R3ImlixGwcQ2CN1zUOa9bSoQDUXqURMII9wgIxBUhrYcJ4qTvtdBdqzVRTvJ4vtbyP9MsU4wAPgAgIGLM4HCYijz+yoAHBf4RGomgg4nFMadw/V92WJiXwIMF1D/muPnMmfDMlupok6IZ2hLs1bwfgqLbWxPJTYlVK+o+h41iA1i6eFNir0l8sOqEICztDOUFUs0SBZWmWASvUXdirKQs5OXKXZe4r8jV+GUN8nYMEt1qsxOmYRoGfp58EXFmhzw3VRnLdJn1kCgwjyjEv56tpnQ3eUO1Y4lDlio9LYjaBU7LGj++TE13O0bWyAOS7z/lmok3VA7cBFOFwW/N8HsToq5ALGZ00O/aIaS2Fs/m4IokuJ7Cgu9KlmVewIDTdsgVKwbQo89sTCvyOgZNYgfAPhLxzUQfgyRzJPZCXU4LTuKgiEAHIVesbsuz4Qruw8VBP/NfCdUEP06qlgWKoixKRAfQLRMGYlX+8QyRFuKNDzbVAyZiXhREEH4Yv/pdm0zOGn6jQAAAABJRU5ErkJggg==",
    "X": "iVBORw0KGgoAAAANSUhEUgAAADQAAAA8CAYAAAApK5mGAAACBUlEQVR42u1Yy0rDQBQ90wYUFJVWUHStlG6KG6tLxYXf6Jco6trHQt0UKa5tBR9YWnFTGRemEIamyc28xxwYmmTCZE7vnXPPDBs+niAkVBAYSkIloZLQTPC43YRAiCeud20S4gDe49+xwnFPTRLiiQYAtfi3KjyngAF4StwfmCLEiaQp2E5cz5ki9BGaytUJ7/4UjP6XaVFgcRtk9EcFU3nRlsqtCBOZEKGi41JhZQrGaOYdz3RhfdComkYI9YT7llCjxqqjHRWY5CuAEYB1APOShKspEWCxu6hRB4wKhn3VoG+boBua227oIpRHei8E30VxGSylKUs5nrIosz5yCWBLo5RLR2hAHPvQRS/HhaqfF3cZ/S++bcF3MvrXbBNi8ASVHOk21GlVbERoyWDx1EboKuXa25RLPt+znUYqCLUlxnybIihp5wwj1YSiDGXjitZFPaV/wbQoULzUOIfcX7ugcpS9TRb2fSJkcltuhVBed9FykdAn4d1bneGOFFTyZwDLhOi0ddY1FRHadMkG6VhDZzbdO2X7MGldzDgsB3DsutsWLUoDf4fl4iFGH8C9hAp2dIsC1aJsSM6lqTNCPXiKiqZ/W3XxVea2TYPLftcFL8dMpBxCW0M2wUMgxEJPOR7iGvr2nVBfuJ8HcO4zoWnF/Ojfy3bk2Hyk1a4srCWhkpAcfgFaBldPgehOCgAAAABJRU5ErkJggg==",
    "Y": "iVBORw0KGgoAAAANSUhEUgAAADMAAAA6CAYAAAAdrmHiAAACVUlEQVR42u2Zz2sVMRDHP/ustYr4hHqw9aJ4EPyB9iIW2p4UtH+if0itqFCeh4eXqqBIFXn10hYq2tKq1Us8mEJY8t5LsrNxE3ZgIQmzk/1mZr6ZZIuDD4/JRTpkJC2YFkwGYNaAQ0ABe0CvzskmarC5B3Qt411gUQMrUvFM10FH6ed9Tjlzvelg3uZEAHd0Tmw66BZNJ4BjuWLkRy0f3+4zFeRjTDDSYdYHzun2KeCqhZIBNoDvuj0fG0wPWLDE/B9gMmDeaxaA5Zw6Hn8OPJACs6J3bptMCntWWcbuS+bMowbk9lZObDYjAaZf6r/UcT3uGSdPhOx4gblntH8AS0IrvRzwTk8yzM4Khs0bRz3TO4vAaigYFfih6w46NwNtX5TwjE/8zjnonPCwZ859Owc2MwH99gWzFeiVX0b7SGLv8NmoOw687jPp1JB28N4xJIefhYbZjCMZrEUMtXkfMN8CT5guchRgu7yYZ3zATAPbRv+Tw4TDbmVelxZnSsBLHd+qeVY4NFRFO8qoRGql5leB7w08ARWjKhEpMHctY+8c3juZyh3ArVJ/26JzKQaYvo7RQ+CFpl0F7JT0VoFd3T4YQxiz1CzFkN+ASjDxx9ktUgiz6FIHmCIFMPs5eea85Yz+FPhq6Hx2rKhr8WLVG82HgRV1MjmTRJh9qTDPegyi8AFT5UZ/LoZnJv4TvW7GBCMpu7EWKgYBXCj1V3Jis+WcwAxyAnNZoCpv3KY5SBGMGuGh5Ki5o4vMn/y7+JgGbjDizrjJYABOp3o4y+qk2YJpwZTkL6j1Xiy/cuYNAAAAAElFTkSuQmCC",
    "Z": "iVBORw0KGgoAAAANSUhEUgAAADQAAAA6CAYAAAD/cnqbAAACEElEQVR42u1ZS0sDMRCerF4EUbQo+DgoVS9exMOCIHhQsf5Ff4hUFqG+wJ6kFz1o0YPai4pQRA/SeIkQlmQ3z80m3YFAttkk83VmvkxmUf/uCEKSCAKTClAFKGBArSI2GbW0bgIAe4zfceoZ+QAIh+RyOLQY+ggNUI3ERSfnvTMb8WOTFDY4boh8s9DQHayvvgJ6IK6WZr05MlYKQFii1TPWqQvMHwBAu0ykoCsIAGIVQokkrONasK0YQlQ7KYKKTcdQltkbDJBIECQSbLQ8h3AO0aAWdAHRTPNjWNG2C5eLqf6Y4b1jiXd7JgA1qf6NgsJdhuuoZuPzomyXBeiA6m8qKDHFAFfTsOitqYNVhZYxJztIy6/E4b5OrTHgGYNnoU+qf2zx1jpigPmEAE1S/cOS0LfRTOHUoqItF9n2ruY+HeImT4yxHYX1LmRJAVFmNpGr/V/JlzUSXSSiT6QafIZP/3ddMrCVy8WKSk37VFO4Cq1Isi1oJewLIBnX49UYHgHg3OeaQlqWSMutMVSFRsPSzxl/cQ1INtgnAOANAK459YRFiRpFaVxuBgC2FOYlRQEqqqy179JCieb8b1FXtgWIttI979+UEFaB5suVhVbBTMkqTRjjLl0uJnUAr88h5IIsiqbty9AAzfoMiEWra74CcvaBzAagZmjZdoMwWhfkP4KVOoZWhvE+VAGqAPkufxj3ZgYDq6RHAAAAAElFTkSuQmCC",
}


def normalize_text(text: str) -> str:
    """Převede českou diakritiku pryč a text na velká písmena."""
    normalized = unicodedata.normalize("NFKD", text)
    normalized = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    return normalized.upper()


def encrypt(text: str) -> str:
    """Připraví text pro kreslenou šifru Tančící figurky."""
    return normalize_text(text)


def decrypt(text: str) -> str:
    """Textové / interní dešifrování.

    Kreslený výstup nejde spolehlivě číst z obyčejného textu, proto podporuje:
    - běžný text: AHOJ? -> AHOJ?
    - hranatý zápis: [A][H][O][J]? -> AHOJ?
    """
    cleaned = text.strip()
    if not cleaned:
        return ""

    result = []
    index = 0

    while index < len(cleaned):
        char = cleaned[index]

        if char == "[":
            end = cleaned.find("]", index + 1)
            if end != -1:
                token = cleaned[index + 1:end].strip()
                if len(token) == 1:
                    result.append(normalize_text(token))
                    index = end + 1
                    continue

        result.append(char)
        index += 1

    return normalize_text("".join(result))



# Grafická vrstva pro vykreslení výsledku v Qt rozhraní.
class TanciciFigurkyOutputWidget(QWidget):
    """Kreslený výstup šifry Tančící figurky."""

    _pixmap_cache = {}

    def __init__(self, parent=None):
        """Pomocná funkce používaná interní logikou šifry."""
        super().__init__(parent)
        self.cipher_text = ""
        self.scale_value = 1.0
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setStyleSheet("background: transparent;")
        self.setMinimumHeight(190)

    @classmethod
    def get_pixmap(cls, letter: str) -> QPixmap:
        """Vrátí grafický symbol pro zadaný znak nebo prázdný obrázek při chybě."""
        if letter in cls._pixmap_cache:
            return cls._pixmap_cache[letter]

        pixmap = QPixmap()
        data = GLYPH_IMAGES.get(letter)
        if data:
            pixmap.loadFromData(base64.b64decode(data), "PNG")

        cls._pixmap_cache[letter] = pixmap
        return pixmap

    def set_scale(self, scale: float):
        """Nastaví měřítko vykreslení a aktualizuje rozměry widgetu."""
        self.scale_value = max(0.55, float(scale))
        self.update_content_size()
        self.update()

    def set_cipher_text(self, text: str):
        """Nastaví text určený pro vykreslení a obnoví obsah widgetu."""
        self.cipher_text = normalize_text(text)
        self.update_content_size()
        QTimer.singleShot(0, self.update_content_size)
        self.update()

    def clear(self):
        """Vymaže aktuální obsah widgetu a obnoví jeho vykreslení."""
        self.cipher_text = ""
        self.update_content_size()
        self.update()

    def resizeEvent(self, event):
        """Reaguje na změnu velikosti widgetu a přepočítá rozložení obsahu."""
        super().resizeEvent(event)
        self.update_content_size()

    def get_metrics(self):
        """Pomocná funkce používaná interní logikou šifry."""
        cell_w = max(50, int(72 * self.scale_value))
        cell_h = max(66, int(94 * self.scale_value))
        letter_gap = max(6, int(10 * self.scale_value))
        word_gap = max(24, int(38 * self.scale_value))
        line_gap = max(10, int(16 * self.scale_value))
        return cell_w, cell_h, letter_gap, word_gap, line_gap

    def char_width(self, char: str) -> int:
        """Vrátí šířku potřebnou pro vykreslení jednoho znaku."""
        cell_w, _, _, word_gap, _ = self.get_metrics()

        if char == " ":
            return word_gap

        if char in GLYPH_IMAGES:
            return cell_w

        return max(24, int(34 * self.scale_value))

    def calculate_required_height(self, available_width: int) -> int:
        """Spočítá minimální výšku potřebnou pro zobrazení celého obsahu."""
        margin_left = 14
        margin_right = 14
        margin_top = 10
        margin_bottom = 18

        _, cell_h, letter_gap, _, line_gap = self.get_metrics()
        content_width = max(160, available_width - margin_left - margin_right)

        if not self.cipher_text:
            return max(170, cell_h + margin_top + margin_bottom)

        x = 0
        y = 0

        for char in self.cipher_text:
            if char == "\n":
                x = 0
                y += cell_h + line_gap
                continue

            char_w = self.char_width(char)

            if x > 0 and x + char_w > content_width:
                x = 0
                y += cell_h + line_gap

            x += char_w
            if char != " ":
                x += letter_gap

        return max(170, y + cell_h + margin_top + margin_bottom)

    def update_content_size(self):
        """Aktualizuje minimální velikost widgetu podle aktuálního obsahu."""
        parent = self.parentWidget()
        width = self.width()

        if parent is not None and parent.width() > 20:
            width = parent.width()

        width = max(260, width)
        needed_height = self.calculate_required_height(width)

        self.setMinimumSize(width, needed_height)
        if self.width() != width or self.height() != needed_height:
            self.resize(width, needed_height)

    def paintEvent(self, event):
        """Vykreslí aktuální obsah widgetu pomocí QPainteru."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
        painter.setRenderHint(QPainter.TextAntialiasing, True)

        rect = self.rect().adjusted(14, 10, -14, -10)

        if not self.cipher_text:
            painter.setFont(QFont("Georgia", max(10, int(14 * self.scale_value))))
            painter.setPen(QColor("#a8a295"))
            painter.drawText(rect, Qt.AlignLeft | Qt.AlignTop, "Kreslený výsledek se objeví zde...")
            return

        cell_w, cell_h, letter_gap, _, line_gap = self.get_metrics()
        x = rect.left()
        y = rect.top()

        for char in self.cipher_text:
            if char == "\n":
                x = rect.left()
                y += cell_h + line_gap
                continue

            char_w = self.char_width(char)

            if x > rect.left() and x + char_w > rect.right():
                x = rect.left()
                y += cell_h + line_gap

            if char == " ":
                x += char_w
                continue

            if char in GLYPH_IMAGES:
                self.draw_dancing_letter(painter, QRectF(x, y, cell_w, cell_h), char)
                x += cell_w + letter_gap
            else:
                self.draw_plain_symbol(painter, QRectF(x, y, char_w, cell_h), char)
                x += char_w + letter_gap

    def draw_dancing_letter(self, painter: QPainter, rect: QRectF, letter: str):
        """Pomocná funkce používaná interní logikou šifry."""
        pixmap = self.get_pixmap(letter)
        if pixmap.isNull():
            return

        target = pixmap.scaled(
            int(rect.width()),
            int(rect.height()),
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation,
        )

        draw_x = rect.left() + (rect.width() - target.width()) / 2
        draw_y = rect.top() + (rect.height() - target.height()) / 2

        painter.drawPixmap(int(draw_x), int(draw_y), target)

    def draw_plain_symbol(self, painter: QPainter, rect: QRectF, symbol: str):
        """Pomocná funkce používaná interní logikou šifry."""
        font = QFont("Georgia", max(18, int(38 * self.scale_value)), QFont.Bold)
        painter.setFont(font)
        painter.setPen(QColor("#f3d79a"))
        painter.drawText(rect, Qt.AlignCenter, symbol)


if __name__ == "__main__":
    sample = "Ahoj jak se máš?"
    print("Vstup:", sample)
    print("Data pro kreslení:", encrypt(sample))
    print("Dešifrování:", decrypt("[A][H][O][J] [J][A][K] ?"))
