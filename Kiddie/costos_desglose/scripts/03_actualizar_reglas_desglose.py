# -*- coding: utf-8 -*-
"""
================================================================================
03 - ACTUALIZACIÓN DE REGLAS DE LISTA DE PRECIOS "DESGLOSE - VENTA POR UNIDAD"
================================================================================
Ajusta la fórmula de la lista 'Desglose - Venta por Unidad (ARS)' para los 969
productos, aplicando el margen de desglose (margen7) directamente sobre el
costo unitario normalizado (standard_price).
"""
import base64
import gzip
import json
import os

h('03 - ACTUALIZACIÓN DE REGLAS DE LISTA "DESGLOSE - VENTA POR UNIDAD"')

# -------------------------------------------------------------------------
# CONFIGURACIÓN
# -------------------------------------------------------------------------
env_dry_run = os.environ.get('DRY_RUN', '1').lower()
DRY_RUN = env_dry_run not in ('0', 'false', 'no')

mode_str = 'DRY-RUN (Simulación sin persistir)' if DRY_RUN else 'PRODUCCIÓN (PERSISTENTE / COMMIT)'
sub('Modo de Ejecución: %s' % mode_str)

# -------------------------------------------------------------------------
# 1. BÚSQUEDA DE LA LISTA DE PRECIOS "DESGLOSE"
# -------------------------------------------------------------------------
sub('1. Búsqueda de Lista de Precios de Desglose')
Pricelist = env['product.pricelist']
PricelistItem = env['product.pricelist.item']
Template = env['product.template']

pl_desglose = Pricelist.search([('name', 'ilike', 'Desglose - Venta por Unidad')], limit=1)
if not pl_desglose:
    pl_desglose = Pricelist.search([('name', 'ilike', 'Desglose')], limit=1)

if not pl_desglose:
    print('[!] ERROR: No se encontró la lista de precios "Desglose - Venta por Unidad".')
    print('    Listas existentes: %s' % Pricelist.search([]).mapped('name'))
else:
    print('[*] Lista encontrada: [%s] %s (Moneda: %s)' % (
        pl_desglose.id, pl_desglose.name, pl_desglose.currency_id.name
    ))

# -------------------------------------------------------------------------
# 2. CARGA DEL PAYLOAD
# -------------------------------------------------------------------------
PAYLOAD_B64 = '''H4sIAAAAAAAA/5V9WZIju67kXs53GowYCJJ3K9d6JW299zYHyJB0kvme8FNWqnJIERxAjM7/+8/g9s9//juaq1PX+SOtUfvRrsRTxo/lJ2o/vVH7Pz//iI/+z3/+q3240hz2w4L/lenEzG/49eD9n//812Rxo2a+8WpKMptdBcY///lvb20IDdEtYK1RnzyvAhMCQ3jSXOMI9EGjs1wFFgSMVciH/Qje7UcYI9DGTWBikPrqLLT0vLMNJ27arwL8z3/+62qs5NbPL3Ql7+Y/FkPQPgTkn//8l9vofVCXsSVMG4k2vkpo8ScWJo5dWyNv84djptmVWnPO5/8QGIxxHT61Ux9r/4K2QWqil18YvGqPNKRVBaQqoMV3EKsKeFFAW3Gqh3JVwvHabCw0lM9UG7EMfVuuI+HWOl6aV1vkPGOr/+gkXmI/TO0npLcCsNZjHa1lxK4bvGhO1RsYoyNrKc3lCe6L5hjrAT9Q7HsdnamNRI5OTfj6DFiatmzQOl+7Jq2+1g0c2310IZeeYOZOrUu/oB3To00aif9I/h9T49vbOSZGdRm5rA32hTG/PbRj8ZoNIZ0bLaLkvK7PgSm05UbT50bbJDEooN9oTIqxG1kfPwvLw4UGjwu4h3YabJ14zLOJJvXZRq4jmdR+/IHjuWcbg1jP4lMhbbNf4Xjw1dqitvTAnZq6XeGx9lT67GQmW7ly80bYVFukf4jECpTZRIixRnN9y2wkwnIViV2qg0mUzysvsmnr9lAr9uhYzEZj9vNQpkKLp95+YcUm9Tm7kWIvbP06J3XTu0go/bW6OrmPI7JWJ8XnmwgGdw4XEn0Gt1OzeX+PGFzm5cR+lJPhnew61XFGjNYn2Thv3Z3Mx7zCMapTBmbunNTuJDgVb3DscJ4du6+fpxnWyFzs+rbY5ixtDCWXYzwsd+LnfT8FsNVleNdG9qw+5ubEclsYqY212ySTc6BAUy4s9YCfPxKO8VdXc5q6rSWeTEPtXRHHTKaAfQjs7++kE6r4l0Af1mvKvg+rnUC+cv906K3ZZAs4Q1p++uuZtsLwFbuHdRjTmNC3MSaDbOrWvv8WiIlbYyxinBH7kOh96vUHYr+JLe408QwhYIum4jy6CWC3ibQltA7ciGf/Ax47bXZh6nYsvmHUpt/fOPYZiw4hWWeIDArjOkSjxTqSzk0GzXn2Mv6BZMwVC+5jGkaLY13EBafj8CMiDitzzqsI3kO8mfVYHFvEG/R+14uIxoMZQ3szXiSU0qA2rV/hXIPjgXSNSbP3sx8WzWX3h8GwCi+DjjxLdQ4aY9gVj90ztRuJ2D66/6enCd9ktkm68O0xQ0KqfkXHvhmr0RCsCQCY4yi/ocf7d+cCgla9zZNqrP/Ze6PhZ1yW0ICPdcNDb6kxU48NiQdX6N3GN7iFP8Kq1BcO8NBQndT0+ugWR9NwXtTnOfBHIxvzOuoWhor3ReLbHFxwCPsFPX2EESTMQsZ7L3pM2HzzKrofeGjQMdYiPvCB82DKFR6GjTLMOzxLLBgnXfcvD7tw9oX1uNFrEDTRDR5+HczfQf35cqa2+vVZwm7qzadRx2pMxc2kvviKz3FUWNxHSy0hh9K9wTEyXcItfb7dSPyPp0kbeEIPP9++yHu/ouNknLA+53POMcxyths+NLJKU6blBy8TLsR15EMh21rS6Pl6PM3HrHo/6NBjy9loHXOMeRJMiuu3x6LRaZ38wStOURgOF3ycurMNp8fcC03Q7mOZvvHAVJ6hbzg+x4/YsQHOET0H4+mHjEkMIynMCafO0vdpiz8SvHqLRbBkkBxPzBbJEL6cI6u3WASdneY8Tnrv0DPrjrciHm/apyq5P/gJFTnueChJX/BqrG+8L/I1+h0PNTmmT8IRlvgxYcr/8TyhKRt7ozUfV7UxecN+v0lgJS8TJZjVKbCMRO1mW6weES5u8G7haO0fgHey7q/AoS5FtRH3cyyzKGljv0uEeWGdmVgfCfhXzHaXiIPQ4FQ1Wecct0ZjtD9eI0x5H6uT8LEkfRBP6JabQK5pZ6XRHmu7kXW7DyyHlWfTGjFCgcdbV29/vHbY876GwLt7PdKc8764I6Ik2vzd81xC4nD5bwKptbwtUn7UEBuZjvswRUhJfA4jfyw9btCRsFxvEnl+Cc5bW2+qbtnVmlw9olDaEdVQfiRMaQ3946nCmVfjhkDJkYBXY3pfhBGHcm1zpv+/I11C2vtNgpvF1v4uigO0l9Dj66AP0LOEXv9rjOgNHdv5ezR/G1QCWCpg/ToEBbSV0P37iBXgXoOPbyNcAM8KeH0fD+NmsVcLcP4+fga41OCFeBvgVoOHGTsksyzIhfzgyTw+XeBeg4+vo39AzxI65rSpkhj/eKSCOnVrckNnOOVLtMcU/e8Gtb8EtCpgFZOdm4fn1q13CnMH/wdf23ZAK/6Yz9dbLePBzXsx+g8RLsV3ICFliVo2iduMmJCO1WfGO9J/bko+bolAbitCCx2WsJ0jUMI2uYQiAY/FYa3DDHseiRFebDAF/hXKg0QER7szDT9HvxqJDb7/AhbHkjlowUlP/CDuvO54bGIfbdA60U6MkKvd4XFmdnaGS/mYhbDVkSv9FYyESBhIkcrkdQLbMoR48s3K47YiFiAI3ZKNJyJkndbdzoNIZCd5GekTQ3KmBXv6LpAHI5ARF8543mBq7a/fyNAtTx+0zlzYIBt8iSQzr9hJZqsbPQHAuWjBC/i9T4UtBrfBgNaByYskscJ3/x2kAH4W8XieOaYhUrvP1NHJ5xg3/AgDydSdhpwIDmxQ+GGwIhKPvyU+nYzWI3CXTuQcBN8yvOTPqDDw4TC4DGLkSGIrTFri4w98PD8vhmLfMzaZFo8/fiAO49XYEJrfXlUjtr7+wGcwxJw0QsL7f5dggK4CoZQQQEMIYbvkiKB1/0MgYrBtDcsAR7xzhGDnHwLpIokR4sC5YGCC8l+v4BW8cot9MxARQS4iPe217iOqHJ7/wNP72mECo66L/4CnAdLJdM+wMcm8Do5yGJSCcMi2+BoCEBpn0zEBD1gci4F9jBZefyo67WSsFlngz9WsmlZflGxwHNzn7y/w61ksko/cpxKb/WQc1cllztuXm2OrrMkky8JEQBFCt3UFZ/xvYZVBH2b0xPHhgk5ffwp1Sewk6dAmR9O+xqSHXcMOnyc2yH6OiU+vDR6RWwhYy/AcrN+OVFRGTpg6d708i7VMbDYdTk8+gJvS8DnuAhG9Nl8k/eh+NfIl/Y4f20V8RZZQzTGFr/BMUHJkq+xscWamyeM9ZPgocWsZFtOGuB9s8hSBrTJxgF1EJOJRsyEHcAYScWp39W0UxD/thBqbxKZd0vHaiNJiQUiPUNx1/ZhlOHvOjrhu7hTuA/GcO36EIzAaRUozfVFBVicOrjDd59bLZhGeRjhPj1rujbrAafuF7hKHL2tDnmu+D9BYT63SxzLqeTD21oSWbdMep53g09vT75/wFgOqYk4cOSIgxMjx6YaPg6UvmeTIpsf3L6GJTxd8Or3f5hKA1yLeivheSEAB70X8KOJnEb9q+Dh3C/jI9i4XMhuhms/fX1bGo5rdIhA++6LeOJfzQIar820zeo+cgq+woE+6vXfyZRcLGnl5L1hVwI+CVQX8LOIrVpu0EQmgCp7f8enydMa73983S2cKeC3irYjvRbwX8aOInwXlAHwlTyptZBargI880/RGI4LHcbQYmcDkvOGtiO9FfIy/z0EWHmpYBDuWfcWPIn4W8auEn60V8VzEh4ndDGHxPb8yOfXVFR+1aR1xtYiLRNCbqbnKHW8l/TYzBF/A1/TnzDD89/iwT3QOlNUcm1Unjb7eIjRzHHio82XNqPsOscB85Sn34Q91y43xDf0njaWlhLhzmBqPV7jxoW6ZUdqNOoQ4XCLtcvFxpK1IIyx2ocZHm7iToU7x8jgrEgnfHqXSVngLFTx/X14iOxxVgFuxtkc4i3t02aQoHwzbFhHp8dvUE866jq9XD6tpCe/hZvY5mLifmDiWA/baDT9aEc9FvBTxWsRbEd+LeC/iRxE/i/ji/GbbRAFfnN+wrir44vyGdVXBF+c3rKsKvji/aV0V8MX5Deuqgo/TfclCiHcbhyjOutXQAS41uNbgVoN/zm1YGmo0za+a2dNy+/7rRw0+a/BVgY+02r6Hl6Z1hM1WgJemdWT86Xt4r8FLs5pJgQK8NKsjzJ3vt1+2+lXwNXWcZXEVfE0dj4jYus1BjoA6/tNtIlLxHjo+IV7hrO0vCVSKn4HPynu0Gq6n2A2+xSUQKTwyWjhcGhnCMRktHMhoXsLZwiPbnBqqRqJILOwvo4FPF4uZV1gYrBNBYRTUnoDkRFwYmbR/5xwhEz7IcLdF/GoMHLC012ee8liSKywNV5kkqEjIOFFDYOmSOQU+8posyEgbyvx2gqyhGlb/eK4oC2ptsJIi4Zr2cGvoQ9JL+4fwCosjLKf3IDf+AQHTfpeJMnwdgij3OtOSpf/Iuv6WWbuDYrROeONd+Eafkff5QkcTnCmK2E6eedHoQ+9wDK6gepafHp9JAznqKzyLrZogzbCr/MiZ/0DHqLItZKKeL4/q6xs8j3iJxtenb6rR7Dzu+BjM6Lfx0zaB1hrzOzw8EkGZ7jjwTtz6/eEzPGOCNOOrDBhL6I+nidzCbITS3J3fpyXtj2/PUvOGboynhhllu389zd79xHLqrxktxPdZjRP+e3T03gpadZ9acDLjP2Yp/PCOTFA7NfVKjd1+w7W1ON9RURC9LQfuyONe4XECz9bhtO9M8qSGVoLfXr62bFL58hgDPDLbKLObGaXe+1yYbPa7SBbpiBsNBB52bhhRiHlpEdfWtuvbPQooTz2CkNi6FG9AoHI4AV+wOwDvNbgX4obAFwwPbS0c8eEN/ZAnM0+CwpzXemjUeKO5hJYKOpSZCmqu/PSCijdSv/TZa8scO2ISiB9jBntDFe9emfa5MjNpjloTWm1nk1EFs9bt/AU+zD1bg04Friqt9bSYfiwZjkzRQvIPHaNZQUHIDf7xMLlpsQvxqrs4CBW4fheIOjCxqVBKKKjLdbAmqgTHJaikjbdBgPbGnWzk8Fr+GKA415Xl1cNBH8nnRylwnrRvzWv5MJMbab8EXyGS+tVQdpCAQYLKwNujSIy99Oa0TpeFwKpBJVX/d3BLm2RW2AQ685wNHV0RaBz7lamGQPSgNJudxE6zkDVaUCl3iVCEhojl23oYKJG5DJHEpsXX4xF25wcqTXZWdv/xgod3j+o4P/BOMsCZcYFnsYuMiez0rlRER0oU/f7O7aGQPKxhrHdUu7xVfX2o/dfrrijr6O7k7excJlW55Q615VneUVwZJWJRHdEIVtfvxcCZ1v6edwTFN+Pb+OjZkuwZX5/oK8U+3BV+Mzs5UiCX7ZGYcbQM1oWodOb/oSG66nuCFYs98WHTmygqTWAJP28Bg+qXia4oiIumMOx0PTY9em/x6VfQVnmFh2o6FqHRI/E6aOHTFR9WSXOJ0qDAj+Yk+HTDZ5vIXIKNdtTQhFJafBVIhgyb0T27fwD6BZ9u+Byhb50YCIRBq/DC9saPNnzUtt/xUKRjOeE0RLsWTOeGdqUrPCpwRZEzmrsuixf07rUwCwLZPtmF0DGUAuYotPnjBaL8VteihWagWBJKKvMPdOaAkDPtHNVTKHKdo8kf+FHEzyJ+1fBBmFHBcxEvRbwW8VbE9yI+kmoNhuRJwS2CbfEG1zd4VMfBWnva4RZ1lM3e4bt/Dv12T1FXI0a/3V1gT++ip1oYXUnokL3iwzZkRjQgTIh9DjjKxO8CMb/a0d/7/AIMtI/S1neBmOCOJ3rVpSFjiaPjKhBZd/RtPzXSSgsK/goPu2MMgQ/bs6FTBUwGf2zfrKtb0UN8nAM0NCzYNTeBdEsb1CzKa+PwGgg5dHTB/5YQidgGVFAU8Tx16vY+BwesJ2uKfsJTK68+iYe+u4Pn1BPdRjRqDbv+sEULK3yd+f44YcBsgYgkNodxO7aAoonU/S4QrjI6LmnoPq07ogj6nsk9RW8qFh5nAR+hQVYmR7XzXkGMD3FoZwTlhbYSupfQXkKPEnpV0FFwzeoIIby2Oqhj0K/w++SV7FHqiAx1foI36IC6uC+SLUqvFpAT1BukbcnvFhBIfBKPbP4XNvJ5axpRseCOGssihZymwyLUmV7cL/EIr8roMOPbLuPtPXtsX7bVgx+hOtm1k4A4rp3SYnzSXwa6jNCdfQjM7FMqOVA8POSO39VHSm1/vRoTQjgv23NzaqmMVJzZaX1MTycfH2v+pRNGqkEZTANdgWlnDmJ8uglkMUjBhJYZCYYRxbnjWRATpvGFrwf4aLUWw3mFvvw0uMGUc2niUJmxEb+q7FaZ2alrc41o/zuNK5PWcL2t5xk7QBQtOr4nAIp58B/4iCwZemHCNg/LUwz+0iU+D3yWqqKWGGXvsR640/gsfH/Dh4OE5XAmDLVu+HBFZzsQgnqIw+QEY701fLxJhIcafZ1YM/FqE5yIekePSoxIZrR8GYiJUDidkVpHs87ty/vb0NjH0NzxkVSYCw77aUpAqbnCC3kt5jd8BKxAnqPMG99AwcB2xWf4YTXomlPaj0Klj16MNzjX4FKDaw1uNXivwb0GHzX4rMFXCZ40UN/Da7O6SUe+htdmNXINBXhtViPXUIDXZjWyDV/DV3RyfX8ur2jkquDj2JnguDsOxKIJBqiLqskyOxPQi53eponwAtvbl4u+8FbD5w75/pzSFnbL15pY26aW+h4/i/hKXaRqy4hNAc9FvBTxWsT3It6L+EoVLvCziF81fES0vq2TBZ6L3y9FvBaquIG3Ir4X8TFfYECOzMfj2EyUEVwFIpODyPJCL2ZqIKcGSsnfClGTYRZ0ACCNeUVVMAUYootEBM082LhA1JTG/gIhw7zjMWXLFtMTi5/Qie0PeMyYokdOI8Ub2YFBo92/n+Ow6+gPRcQgFPQg0ALcYv2aXX7DGtreTt0LnDqet1SCSsbhO5g7W1ALRa8iWtQ+7MEnAqCSle4liVmWWFWJ8NHEfAoH39Yhqgwin48ylnMYSBQV49RBXwKfdHuHqY2ug6tIpilVg0bvOGogQbXu6ypSMoVwxNbgFVNIk/0QaoPcdleVMzJTp+vgc3VoRoT7Eu/UIyYfPyEDjNUPUW288COTlKSoyHP07J6Mvk8SRwzu8lhxkBdFZl1kVUUsCix4emdCFPnkYEApd+kUhkC0EWH8o/5hh0AZzuG4uapqcWQJeqtAB5CPZGjqvQYoNUmxVlKRPgQiqK+48rGqerJ3N13UHsZxbaQLdGbPA4HG/wjEOK05yXg72yB5nPh00zkeq+SPGGJ8+NcTJYXrQFh58Y8hUqGDBLy7l8ScZkHw9/isBeWGesJH5VO7dg4CnWfQpPaaYUJK6IaNLkyU25zwNvTyjRFWNVkSRAU8pvp8N/6BMPaXvZNdg9xDe+8wHMZt4dPrJ15qL9viBHQwfe0ToTsYXN8Pk3d8eCvaFmLOe7VBX1wz07qiTrMLqCa7RBWHd4SiP+z9o+qSRobdOxrZ+9lg7h5sJpf3TSYZZl0O6plD24yO84mys5cINucWCROGGdn7dmJr1nrkMG8CSdtsqOxB8vfhAARlyotP5kNpZ6rnrlYve3gXUa4m4KjYXtREXY3ewpW6yw5XA4MOahQOe543lIldT6usgXNREHMgzhS8JDgf+9ipkI+HsrTNxRrTOgQNoDFkfPodFTWO7JyC0Rffz29MFJdCODXNaD33GVwqyAvhJBSEid5HCT33WyJUV6Z7/ASZg8b5o37yXUCqAkkmjw0H+tFgLEApKJjALqrCNPm55mwRWQ8BsJf2of0PgagExwna+vkFRO5Bp3oXyNA0aBNwYEawEIFaeKg3fDrNE0dAEnycv1/RkSJFwBmDEilPkCyBwP4PfC/ivYgfNfwo4jNcODhLcaL0CNx625AO9Nkyts0KEybcrhGVgmBGuhNeoLM5+/zWAhnS3jG+4Di8l0092tQsCyQHaiYO3XqHsX1sK/s4+Mwi/ODTxivsDf6zgU9ZUBeq5u0HxrvArqpFKPjpqf2XQDrka3ZwA+/KpkUT5L2vN3iKasw2u5jjeO9bqYDs19+7bl9vkAys06FuwSQa/wsSLD61X/965SRgrQiki91RDIea9z2vqEaXm/K1Hj42alxmkKNm2IgHqcsteG89nOySQGpSUO2KbifP1gLxzQe5wznXrIffXJPoZQkvS4yyRLQ5CAgxzx7D0gI7+SUiZz1MxwI+LMcKXop4K+J7Ee9FfMzAWFHndsKtQVp1hxeHPxKbBXXRoyKkIlArL9j3kFTwo4ifRfwq4b1WHgH2iiJeingt4q2Iz8Q+7lkZ+w440EZ/lsu842vz5eFAVfDF+UoO4gK+OF9xnBXGJ8kBC99fnK8wwiv42n70LO0t4Ivzm6UGBXxxvjIhVsAX5ytrvQv44nyFQ/P490nEzLgcEQbdVWBUBWZVYBUF9m06BQGpCmhVwKoCvSpQnbgw9UsC1YnLJtfvg+rm2blRkggDCvbErp7ElWayiyfTlucXuKiMdqj0+zcOc051gDn1IZkyWuhKfAuuvp4ou2e/t4eSqKMksIoC2RxSESjadPu+0oqAVQV6VcCrAtWJSz69ikB14qJkpiRQnbhV9K1HhlsnKNf5FDKGuw9e3fZ7A43w59xxJzDoyREAZkVHyWnUtc8NNDJ7ivZG1IelAK4Ue1zrXwJc+4Uk5loiu109VBL+RPfTLSa4izHBvoQEcMSGcTcdEmBXfNFky9LKCr5mAsyiyTaLJtssmmwzb375Hl808U4t6fd4KR5S89PIC4GFbsH1F96KeC/ii+faTJutMETFKcsrEwv44pSlgVfAF7dkmncFfHFLpnFXwBe3ZJp2BXxxfvNmggK+OL/ZwFvAF+c3Wvor+OL8Fg3TLPCu4IvzGzHx76MOMxspC/ji/EbZWeX7tYi3Ir4X8bUo18zAeWF8ivMbZlYBH1ZWBV+c3wizV/DF/ZtZywK+uH8za1nAF+c32o0K+AizV/DF8c9KtgK+OP7BVVHBF8c/s8AF/Kzs3573MTzM7PhP9KTfqdkBnzX4KsHDLyzAuQaXGhwrZ/h0asO3++VgZUJ/aXsEjgvZJXmU0TAAL3NXKOGyk/WeVH+N/S4wdTPqURAXvwBiiNbvAhGS//oNJM727x3IbtFCtLThuk5c0LnfuScP20vkZEG7JZd7Xwv0FvmfwdOFOtMbPumqxlKytu15NDU4SggDvxsDjsDOknFrStwf/gw8Mu7W/J2S7pkn+/IaOsDzaoveSXv0q02TvPP9Bv64Vy4LgRpoEvaNM5/wTJF9H4XomSOrCIQ7UvDwegaEzXBN1dpX9iAKyP6+SF8/kHTKE5elg4LsRbUxrle2aPewIBSXoaxgQ8LPow3FtV9/IU8AF5Qw7ryvUF993ipRevIjiyuT+E7U5x2S16rvvq/ulqiF2aGj2GNyrXTpyY+sHZeSkD1shPgHamzv5YzPqk5O3697W3qGFSt4K+IrjP24EzYj8pjkCQa8VAvRGKA3WqSexHDofRPS545NkNww+lqvErP2G56Mb+rSO41TpMSThca89kx4i+1Tksi7Ov4omczI4nvhlLfNHj8Htyj8zLLvidulwSiVu61/iGwqhBUk/+CvyLBHN5L+3MIXIs9jRaCaWfvATXQPww3q7wb4I64/s4M9rRmhl/pwUuBlQaJwlYnd7QwyEH3651mwv7W9X2L3JpMXls3ZjfS5zBr/QB2FqtffSerJhQ4ChG4OXSeaW/xW1Okta+XVTYXQwvJQB+ACQLvVpnoSq+lcK6jGdgNC1Hi+FFU/msfz8rKB045PszsbowL5Q+DoTuc44QU3S/VoKE7VSug0fquywyxtgSz71ca4kfewJTRifLpElZ0zDO24xE4fkwCd7DicrgLJLsmN+j4iULSPOtOLBeG8+wh9kR4CLgOJEj79rnx1jvAPwnzkUaYdRZeCu0jkik+OEBRSvdGy4uqn5R8l8s8OTE62mgSXJfa6mEL87AyNXiTWu4SWJaws0YsSknc/gAcGRKWn+90ElCq/z3qXcG7V0aEeLDJ7iUfR7DvZwusXsoqsDQXN52FmRZPeEue7RDhYU4QJF6Kfem30iLldJcKlQZGhkj4mnbVJjlsm3vbR60VCTeOqJ1BLPFeWodvg6Qz5JRKOqBlW+sPPiUsZVe4CqaYHrnqNm/i2hiIZ/S+JKHFDZ0vMx75NFkkqkAXeXn1+X2bY+xaZtcpE1zg3UZoZ10KeGcEq08fI+3gsjSBpZUdphOnUJ1getqEaF8M/FzV+rkTNMFewkWlWeg9qMq42mOsOci0KKxA6bdFCV+INbVHIZQMuAjyb876T2qMFP143b3pHPa1Qf+iH4RmBuP0qkWmLbgzDNCz958OFkM8toozHqdjX5XXq+PBvL8EtubaWz+gjw7U0wR3XJ/e4tW+/8HHTfN9FeQQ0mJKWEi+d7wLP6Of9gH2CfGrstcw8aHJ/r5Z8/UIPQ4oRLULbxRlTkApi9G4my26+Ak1ps3EMKbBjdXm/C/fgq1UgXi3q8HREUIEu58bFPsnRMn8bpG00O/pOzg5w6qdz9ZOfy0emKkEQ+HKLQJF+qLT+tUhH5KWyJSSc9/6/NGz4yAbgMdGQeHhf4YXh0/UnIvRpDf8yn7ueNZhbxlV3Z4bZbOH/HiUJlWlo+LpJRAwFiV2OpbR/A7daqv0hEScpQ5sorpnf6fpGHb0AV4ls3JholXr4uJmTQPMqEHPhoKgHu9j+CdB/+8edUY9ERsk6mlbJ4Chkr3GQ4oy7RFqwMxgYzonjh4HhcjisyH278kJR8mmWdtyqtN0l+bdAVuTwgBrd/xv9dKJ/CMQOaivOqzwX0IzW7A94NDvKnNGklqZiuBPrD3zS30fD0FbxpjQbbim/4pOwQVrEEtI4EYR5/nj8SH53A/HVMdajMfGv58/k99evm+WN3z9+ZL4LwxOZ78rr9uLrenH9RKq8w6PWYxwyLmxFA+9dYFYFVlEgeyQrAlwVkKqAVgWsKtCrAl4VqM50Us8XBMIWLpDkeV5I8dZBvoMcQfNm/S4idRGtiyS74VIGOecPwng/E/cqG4h8fh+8o4WX5Q3tnv60hTvo2nFv0u/DYTQushCOlrr7a2NmtGyuHCq4YvrQh+AuhM9arTeBIBhGJxfuDU0BMBKbvd+B/cLnXkUzZtNzq2xbZNLeHay3J9oX7c3FNHcVHrQbTJ2Pcd3BELCuVQV6VcCrAuMrgWNjDU4iWm4idPbO36RQg6PrCG4S8kaP/40G/SfF87GSdvwkfNCgywRiCQ18emNNPS8gGcJ6NurmPMDKM6R8fj9S8sEbt4Hr0Q8jPNJOivtGLs8kyQQEd7Id2hdt5PODN+W1MCTbFCNAygdvJLhr/IqPCIItFuJzFuImBQQTfuumIdm49j08z130bs+DDwoKlD1fBbwqMKoCqY5XJKXSM0GUcwiYN64CqyiQl1RWBMIT6AMankH1/BMXs8AavuPDD1gwxjzhHb3kyDZc4foGDw2sEVL6Y84iB/M9fEdu5MTRdtZM8OkSBR2SrdKtg+voUEMwGX/eEvDChw8DAtEIitlDlOR69SWHRLKjck4Njdi1W4/w8NmX+EnGRVtv+/LsfW21U31o3r1WEMjL1yoCNfttaFrRuBsA9488+ehl5teR1aQ9g65lTw6A/fdLwH5oVp/NoTQi8bLTzXBgL7nIkWEtVkTOHnJjxcK4ZfyHRrS0YCYNDV1Xksj7VONmAVzxkWHJhiMB19v3f4fgh6X9Gas9gk/xhkK4EunW6A47KJjYjrIIgcXYb9fo1sjWe27wf+2VaGowflBmchXJgZWgC3vSyIr4xwdf3ZtIxj++PWotTxF4SLHf8hk6bjp7W0fPQW5xigww0K/nygya7vIHHIO6DBdx7dsRxiT31u/wTCLP7p0UJmSaX22C1vkWgh0WKVhGbiXY2+K+BlHqWLfXn9jtwF2CnnLfCOHUQDjyEngpvZ6l1E/pdW41MPb7pmre2/URyORVRYn1ojs2etEdGz1W91og3Toccbg5Q2HLZJDyXwIRHPp6GeWdpjgiaMk+zEBqZeb3B8pbTUsCqyawOZtmM9LmIPWISEOLu1cuKnJs4pavY3RjRuvu12OUbSDfw5MmecoKw/rYqH9Tfo8Mz5UkIhUzDa98PDZEWvmDnqTzfPB5ZxSu4YEVGRewyCLtDdv7d8B3zM/2+P+tc2Gsz/b4L/BcxEsRX3z+CM+Z946VGUbYGB0XVmx/c1tBL3yU/SylhjUXfkv+/YKeeS9SgSFptggvFnzs2eINahJcltAicd7M2o6viQZn1nVU8FrE9yLei/hRxJeIGGfWmBbwUWRawRfnK1Ik3+M5K76X4kq6k0haBObHt63zbMzJWfHtMFcecw3Fjmv2q4CEJurMSjB7Nw0+k+LTJXQ0JVRRIagwJZRRTaIYuJibvrUikRwxyGrHtcKn1HHYx0i98FHLbYqLjjXv5GqDvLVrnGNKmArsAwS0T947aeFupN9TD0MGgnhP6dj/cAPo1OwegxLGrTabdqtTjztuLs+k0e5hgtI/ZJvPfbC4hvVxbj9/IvwLDY/iVYSCeqXxXoPy+om8XOb7XtyZ98uUBNJ7Nh6IWKQELjpWVF3tc/lfEqsqEYdDTYKrEmENL+lBoHUcK+m4A+lWbDt75Bq+z/nMnsWt39bazuTkUO0gPnzxGPJHWehrqpOSIyphnQ8jqqCfWP/Ax1qSBp7EHflzRA1P4a3+Gx9HA+owximYQRWhn5f/hc+rYCaTbkMW/OdIuV3h4Suooqd5okh1Lz2lFT/323aeuyqhMy/U7Z8t2lDrOe4SSULd44LNKGCO/8ftZM8Gejbc//v/6gFfxLy2AAA='''

try:
    raw_json = gzip.decompress(base64.b64decode(PAYLOAD_B64)).decode('utf-8')
    data = json.loads(raw_json)
    print('[*] Payload desempacado correctamente: %s productos con desglose.' % len(data))
except Exception as e:
    print('[!] Error al descomprimir payload: %s' % e)
    data = {}

# -------------------------------------------------------------------------
# 3. ACTUALIZACIÓN DE REGLAS EN product.pricelist.item
# -------------------------------------------------------------------------
if pl_desglose and data:
    sub('2. Actualización de Reglas de Precio (Fórmula standard_price + margen7)')

    creadas = 0
    actualizadas = 0
    sin_cambios = 0
    no_encontrados = 0

    for code, vals in data.items():
        costo_bulto = vals[0]
        ub = vals[1]
        costo_unit = vals[2]
        m1 = vals[3]
        m2 = vals[4]
        m7 = vals[5]

        tmpl = Template.search([('default_code', '=', code)], limit=1)
        if not tmpl:
            no_encontrados += 1
            continue

        # Si margen7 es <= 0, usar margen de público
        margen_final = m7 if m7 > 0 else m1
        nuevo_discount = round(-float(margen_final), 4)

        item = PricelistItem.search([
            ('pricelist_id', '=', pl_desglose.id),
            ('product_tmpl_id', '=', tmpl.id)
        ], limit=1)

        vals_item = {
            'pricelist_id': pl_desglose.id,
            'applied_on': '1_product',
            'product_tmpl_id': tmpl.id,
            'compute_price': 'formula',
            'base': 'standard_price',
            'price_discount': nuevo_discount,
            'price_surcharge': 0.0,
            'price_round': 0.0,
            'price_min_margin': 0.0,
            'price_max_margin': 0.0,
        }

        if item:
            # Verificar si necesita update
            if (item.compute_price != 'formula' or
                item.base != 'standard_price' or
                abs(item.price_discount - nuevo_discount) > 0.001):
                item.write(vals_item)
                actualizadas += 1
                if actualizadas <= 10 or code in ('37324', '710', '2675'):
                    precio_esperado = round(costo_unit * (1.0 + margen_final / 100.0), 2)
                    print('  [%s] Regla actualizada: base=costo, margen=+%.2f%% -> Precio ref: $ %.2f' % (
                        code, margen_final, precio_esperado
                    ))
            else:
                sin_cambios += 1
        else:
            PricelistItem.create(vals_item)
            creadas += 1
            if creadas <= 10:
                print('  [%s] Regla creada: base=costo, margen=+%.2f%%' % (code, margen_final))

    sub('3. Resumen de Reglas de Desglose')
    print('  Total productos procesados : %d' % len(data))
    print('  Reglas actualizadas        : %d' % actualizadas)
    print('  Reglas creadas             : %d' % creadas)
    print('  Reglas ya correctas        : %d' % sin_cambios)
    print('  Productos no encontrados   : %d' % no_encontrados)

# -------------------------------------------------------------------------
# 4. CONTROL TRANSACCIONAL
# -------------------------------------------------------------------------
sub('4. Control Transaccional')
if DRY_RUN:
    env.cr.rollback()
    print('[SIMULACIÓN COMPLETADA] Rollback ejecutado. Ningún dato fue modificado.')
    print('Para aplicar los cambios en la base de datos, ejecutar con DRY_RUN=0.')
else:
    env.cr.commit()
    print('[PRODUCCIÓN / PERSISTIDO] Commit ejecutado exitosamente. Reglas guardadas.')
