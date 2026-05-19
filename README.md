  @staticmethod
    def _collect_monetary_tokens_no_percent(text: str) -> list[str]:
        out: list[str] = []
        for m in _CURRENCY_VAL_RE.finditer(text):
            rest = text[m.end():].lstrip()
            if rest.startswith("%"):
                continue
            out.append(m.group(0))
        return out

    @staticmethod
    def _token_financially_significant(tok: str, val: float) -> bool:
        if abs(val) < _VALUE_EPS:
            return False
        if val >= 1000.0:
            return True
        return bool(_THOUSAND_BR_RE.search(tok))

    @staticmethod
    def _remove_amount_tokens_from_end(text: str, tokens: list[str]) -> str:
        result = text
        for tok in reversed(tokens):
            pos = result.rfind(tok)
            if pos < 0:
                continue
            left = result[:pos].rstrip()
            right = result[pos + len(tok):].lstrip()
            if left and right:
                result = f"{left} {right}"
            else:
                result = left or right
        return re.sub(r"\s+", " ", result).strip()

    def _maybe_recover_zero_columns(
        self,
        first_line: str,
        full_desc: str,
        before_val: float,
        last_val: float,
    ) -> tuple[float, float, str]:
        if abs(before_val) >= _VALUE_EPS or abs(last_val) >= _VALUE_EPS:
            return before_val, last_val, full_desc

        tokens_line = self._collect_monetary_tokens_no_percent(first_line)
        p_line = [parse_currency(t) for t in tokens_line]
        if (
            len(tokens_line) >= 3
            and abs(p_line[-1]) < _VALUE_EPS
            and abs(p_line[-2]) < _VALUE_EPS
        ):
            t_core = list(tokens_line[:-2])
            p_core = list(p_line[:-2])
            while t_core and abs(p_core[-1]) < _VALUE_EPS:
                t_core.pop()
                p_core.pop()
            if t_core:
                if len(t_core) >= 2:
                    nb = parse_currency(t_core[-2])
                    nl = parse_currency(t_core[-1])
                    strip_tokens = [t_core[-2], t_core[-1]]
                else:
                    nb = nl = parse_currency(t_core[-1])
                    strip_tokens = [t_core[-1]]
                if abs(nb) >= _VALUE_EPS or abs(nl) >= _VALUE_EPS:
                    nd = self._remove_amount_tokens_from_end(full_desc, strip_tokens)
                    return nb, nl, self._normalize_description(nd)

        tokens_desc = self._collect_monetary_tokens_no_percent(full_desc)
        p_desc = [parse_currency(t) for t in tokens_desc]
        td = list(tokens_desc)
        pd = list(p_desc)
        while td and abs(pd[-1]) < _VALUE_EPS:
            td.pop()
            pd.pop()
        if not td:
            return before_val, last_val, full_desc
        if len(td) >= 2:
            t1, t2 = td[-2], td[-1]
            v1, v2 = parse_currency(t1), parse_currency(t2)
            if not (
                self._token_financially_significant(t1, v1)
                or self._token_financially_significant(t2, v2)
            ):
                return before_val, last_val, full_desc
            nb, nl = v1, v2
            strip_tokens = [t1, t2]
        else:
            t1 = td[-1]
            v1 = parse_currency(t1)
            if not self._token_financially_significant(t1, v1):
                return before_val, last_val, full_desc
            nb = nl = v1
            strip_tokens = [t1]
        nd = self._remove_amount_tokens_from_end(full_desc, strip_tokens)
        return nb, nl, self._normalize_description(nd)





        before_val, current_val, full_desc = self._maybe_recover_zero_columns(
            lines[idx].strip(), full_desc, before_val, current_val
        )




                if abs(single_val) < _VALUE_EPS:
            year_before_val, last_year_val, full_desc = self._maybe_recover_zero_columns(
                lines[idx].strip(), full_desc, single_val, single_val
            )
        else:
            year_before_val = last_year_val = single_val






_CURRENCY_VAL_RE = re.compile(r"\d[\d.,]*[.,]\d{2}")
_THOUSAND_BR_RE = re.compile(r"\d{1,3}(?:\.\d{3})+,\d{2}")
_VALUE_EPS = 0.005
