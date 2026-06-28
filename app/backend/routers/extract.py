from fastapi import APIRouter, HTTPException, Request, UploadFile

from extract import chart_intake

router = APIRouter()


@router.post("/extract/chart")
async def extract_chart(figure: UploadFile, request: Request):
    # ClawBio data-extractor (X4), end-to-end: drop a bar/line/scatter panel image + an axis
    # calibration -> the recovered series as an editable Statistics table + an editable Plotly
    # figure (same artifacts a skill emits, so it lands in the editor). Calibration-first +
    # vision-grade (confidence 0.7, source: extracted) — never text-exact (sub-spec E4/E6).
    raw = await figure.read()
    q = request.query_params
    try:
        calib = chart_intake.calibration_from_params(q)
        labels = [s for s in q.get("labels", "").split(",") if s] or None
        result = chart_intake.extract_chart(
            raw,
            calib,
            q.get("form", ""),
            labels=labels,
            color=chart_intake.color_from_param(q.get("color")),
            tol=int(q.get("tol", 40)),
            thresh=int(q.get("thresh", 200)),
            step=int(q.get("step", 1)),
            min_size=int(q.get("min_size", 3)),
            series_name=q.get("series_name", "value"),
            x_name=q.get("x_name", "x"),
            y_name=q.get("y_name", "y"),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    series = result["series"]
    return {
        "series": series.model_dump(),       # form + values/points + confidence + note
        "table": result["table"],            # editable Statistics table (S2.1)
        "figure": result["figure"],          # editable Plotly {data, layout}
        "confidence": series.confidence,     # vision-grade; gate before trusting as golden (E4)
        "note": series.note,
    }
