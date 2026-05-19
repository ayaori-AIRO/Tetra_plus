import { useEffect, useRef, useState } from "react";
import { collection, getDocs, query, orderBy } from "firebase/firestore";
import { db } from "./firebase";
import "./App.css";

function App() {
  const [data, setData] = useState([]);
  const [activeTab, setActiveTab] = useState("home");
  const today = new Date();
  const oneYearAgo = new Date(today);
  oneYearAgo.setFullYear(oneYearAgo.getFullYear() - 1);
  const [filterStartYear, setFilterStartYear] = useState(oneYearAgo.getFullYear());
  const [filterStartMonth, setFilterStartMonth] = useState(oneYearAgo.getMonth() + 1);
  const [filterStartDay, setFilterStartDay] = useState(oneYearAgo.getDate());
  const [filterEndYear, setFilterEndYear] = useState(today.getFullYear());
  const [filterEndMonth, setFilterEndMonth] = useState(today.getMonth() + 1);
  const [filterEndDay, setFilterEndDay] = useState(today.getDate());
  const [filterExtinguisher, setFilterExtinguisher] = useState("all");
  const [appliedFilter, setAppliedFilter] = useState(null);
  const [selectedPhotoRecordId, setSelectedPhotoRecordId] = useState("");
  const [expandedPhoto, setExpandedPhoto] = useState(null);
  const [photoZoom, setPhotoZoom] = useState(1);
  const [photoPosition, setPhotoPosition] = useState({ x: 0, y: 0 });
  const [photoDrag, setPhotoDrag] = useState(null);
  const photoModalRef = useRef(null);
  const extinguisherNames = [
    "ID:1 (B1F 복도 A)",
    "ID:2 B1F 복도B",
    "ID:3 B1F 비상구 앞",
  ];

  const filterStartDate = new Date(filterStartYear, filterStartMonth - 1, filterStartDay);
  const filterEndDate = new Date(filterEndYear, filterEndMonth - 1, filterEndDay, 23, 59, 59);
  const yearOptions = Array.from(
    { length: today.getFullYear() - oneYearAgo.getFullYear() + 1 },
    (_, index) => oneYearAgo.getFullYear() + index
  );
  const monthOptions = Array.from({ length: 12 }, (_, index) => index + 1);
  const startDayOptions = Array.from(
    { length: new Date(filterStartYear, filterStartMonth, 0).getDate() },
    (_, index) => index + 1
  );
  const endDayOptions = Array.from(
    { length: new Date(filterEndYear, filterEndMonth, 0).getDate() },
    (_, index) => index + 1
  );

  const getItemTime = (item) => {
    if (!item.time) {
      return null;
    }

    if (typeof item.time.toDate === "function") {
      return item.time.toDate();
    }

    const parsedTime = new Date(item.time);
    return Number.isNaN(parsedTime.getTime()) ? null : parsedTime;
  };

  const formatInspectionTime = (item) => {
    const time = getItemTime(item);

    if (!time) {
      return item.time || "시간 없음";
    }

    const year = time.getFullYear();
    const month = String(time.getMonth() + 1).padStart(2, "0");
    const day = String(time.getDate()).padStart(2, "0");
    const hour = String(time.getHours()).padStart(2, "0");
    const minute = String(time.getMinutes()).padStart(2, "0");
    return `${year}년 ${month}월 ${day}일 ${hour}:${minute}`;
  };

  const getExtinguisherName = (item, index) =>
    extinguisherNames[index % 3] || item.extinguisher_id;

  const filteredRecords = data.filter((item, index) => {
    if (!appliedFilter) {
      return true;
    }

    const itemTime = getItemTime(item);
    const inDateRange = !itemTime || (itemTime >= appliedFilter.startDate && itemTime <= appliedFilter.endDate);
    const inExtinguisherRange =
      appliedFilter.extinguisher === "all" || index % 3 === Number(appliedFilter.extinguisher) - 1;

    return inDateRange && inExtinguisherRange;
  });

  const selectedPhotoRecord = filteredRecords.find((item) => item.id === selectedPhotoRecordId);

  useEffect(() => {
    const loadData = async () => {
      const q = query(
        collection(db, "inspection"),
        orderBy("time", "desc")
      );

      const querySnapshot = await getDocs(q);

      const result = querySnapshot.docs.map((doc) => ({
        id: doc.id,
        ...doc.data(),
      }));

      setData(result);
    };

    loadData();
  }, []);

  const renderTabContent = () => {
    switch (activeTab) {
      case "home":
  return (
    <div
      className="tab-content"
      style={{
        display: "flex",
        gap: "10px",
        height: "100%",
        alignItems: "stretch"
      }}
    >
      <div className="home-live-area">
        <div className="home-live-header">📡 Live</div>
        <div className="home-live-content">
          <div className="live-grid">
            <div className="live-camera-card">
              <div className="live-camera-title">소화기 자동정렬 카메라</div>
              <div className="live-view">
                <div>Not Connected</div>
              </div>
            </div>
            <div className="live-camera-card">
              <div className="live-camera-title">소화기 검사 카메라1</div>
              <div className="live-view">
                <img
                  className="live-stream"
                  src="http://localhost:8000/video/camera1"
                  alt="소화기 검사 카메라1"
                />
              </div>
            </div>
            <div className="live-camera-card">
              <div className="live-camera-title">소화기 검사 카메라2</div>
              <div className="live-view">
                <img
                  className="live-stream"
                  src="http://localhost:8000/video/camera2"
                  alt="소화기 검사 카메라2"
                />
              </div>
            </div>
          </div>
          <div className="inspection-log-panel">
            <div>[22:45:01] ID:1 이동 시작</div>
            <div>[22:45:08] 카메라 촬영 완료</div>
            <div>[22:45:10] 압력게이지 정상</div>
            <div>[22:45:12] OCR 완료</div>
            <div>[22:45:15] 부식 없음</div>
            <div>[22:45:16] 검사 종료</div>
          </div>
        </div>
      </div>

      {/* 🔴 오른쪽 전체 영역 */}
      <div
        style={{
          display: "flex",
          flexDirection: "column",
          width: "140px",
          height: "100%",
          marginTop: "32px",
          justifyContent: "space-between"
        }}
      >
        {/* ───── 위: 개별 검사 박스 ───── */}
        <div>
          {/* 제목 */}
          <div
            style={{
              display: "flex",
              justifyContent: "center",
              alignItems: "center",
              borderTop: "2px solid #444",
              borderLeft: "2px solid #444",
              borderRight: "2px solid #444",
              padding: "4px 8px",
              borderTopLeftRadius: "8px",
              borderTopRightRadius: "8px",
              fontWeight: 600
            }}
          >
            개별 검사
          </div>

          {/* 버튼 영역 */}
          <div
            style={{
              borderLeft: "2px solid #444",
              borderRight: "2px solid #444",
              borderBottom: "2px solid #444",
              borderBottomLeftRadius: "8px",
              borderBottomRightRadius: "8px",
              display: "flex",
              flexDirection: "column",
              gap: "10px",
              padding: "12px"
            }}
          >
            <button>ID : 1</button>
            <button>ID : 2</button>
            <button>ID : 3</button>

            {/* 구분선 */}
            <div
              style={{
                height: "1px",
                background: "#444",
                margin: "6px 0"
              }}
            />

            {/* ───── 아래: 검사 복귀 영역 ───── */}
            <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
              <div
                style={{
                  textAlign: "center",
                  fontWeight: 600
                }}
              >
                검사 · 복귀
              </div>

              {/* 🔵 추가 버튼 2개 */}
              <div style={{ marginTop: "10px", display: "flex", flexDirection: "column", gap: "8px" }}>
                <button
                  style={{
                    backgroundColor: "#007bff",
                    color: "#fff",
                    padding: "6px",
                    border: "none",
                    borderRadius: "4px",
                    cursor: "pointer"
                  }}
                >
                  홈 위치
                </button>

                <button
                  style={{
                    backgroundColor: "#28a745",
                    color: "#fff",
                    padding: "6px",
                    border: "none",
                    borderRadius: "4px",
                    cursor: "pointer"
                  }}
                >
                  검사 실행
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );

      case "id1":
        return (
          <div className="tab-content">
            <p>1번 소화기 상세 정보</p>
            <div className="detail-box">
              <div>위치 : B1F 복도 A</div>
              <div>압력 : 정상</div>
              <div>외관 : 양호</div>
              <div>결과 : 합격</div>
            </div>
          </div>
        );

      case "id2":
        return (
          <div className="tab-content">
            <p>2번 소화기 상세 정보</p>
            <div className="detail-box">
              <div>위치 : B1F 복도 B</div>
              <div>압력 : 낮음</div>
              <div>외관 : 양호</div>
              <div>결과 : 불합격</div>
            </div>
          </div>
        );

      case "id3":
        return (
          <div className="tab-content">
            <p>3번 소화기 상세 정보</p>
            <div className="detail-box">
              <div>위치 : B1F 비상구 앞</div>
              <div>압력 : 정상</div>
              <div>외관 : 오염</div>
              <div>결과 : 불합격</div>
            </div>
          </div>
        );

      case "hardware":
        return (
          <div className="tab-content">
            <div className="hardware-status-list">
              <div className="hardware-status-card">
                <span>상하 이동 모듈</span>
                <div className="connection-row">
                  <span className="connection-dot"></span>
                  <span>연결 안됨</span>
                </div>
              </div>
              <div className="hardware-status-card">
                <span>소화기 회전 모듈</span>
                <div className="connection-row">
                  <span className="connection-dot"></span>
                  <span>연결 안됨</span>
                </div>
              </div>
              <div className="hardware-status-card">
                <span>LED(소화기 내부)</span>
                <input className="neopixel-slider" type="range" min="0" max="100" defaultValue="0" />
              </div>
              <div className="hardware-status-card">
                <span>LED(소화기 외부)</span>
                <input className="neopixel-slider" type="range" min="0" max="100" defaultValue="0" />
              </div>
              <div className="hardware-status-card">
                <span>소화기 검사 카메라</span>
                <div className="connection-row">
                  <span className="connection-dot"></span>
                  <span>연결 안됨</span>
                </div>
              </div>
              <div className="hardware-status-card">
                <span>자동정렬 카메라</span>
                <div className="connection-row">
                  <span className="connection-dot"></span>
                  <span>연결 안됨</span>
                </div>
              </div>
            </div>
          </div>
        );

      case "calendar":
        return (
          <div className="tab-content">
            <div className="monthly-inspection-layout">
              <div className="calendar-photo-panel">
                <div className="photo-date-label">
                  {selectedPhotoRecord
                    ? `${formatInspectionTime(selectedPhotoRecord)} 사진`
                    : "소화기 ID를 선택하면 해당 날짜 사진이 표시됩니다"}
                </div>
                <div className="calendar-photo-stack">
                  <button
                    className="calendar-photo-box"
                    type="button"
                    onClick={() =>
                      {
                      setPhotoZoom(1);
                      setPhotoPosition({ x: 0, y: 0 });
                      setExpandedPhoto({
                        src: "/inspection-images/camera1_pressure_gauge_20260507_011409_1.jpg",
                        alt: "게이지 사진",
                      });
                    }
                    }
                  >
                    <img
                      src="/inspection-images/camera1_pressure_gauge_20260507_011409_1.jpg"
                      alt="게이지 사진"
                    />
                  </button>
                  <button
                    className="calendar-photo-box"
                    type="button"
                    onClick={() =>
                      {
                      setPhotoZoom(1);
                      setPhotoPosition({ x: 0, y: 0 });
                      setExpandedPhoto({
                        src: "/inspection-images/corrosion_2.png",
                        alt: "부식 사진",
                      });
                    }
                    }
                  >
                    <img
                      src="/inspection-images/corrosion_2.png"
                      alt="부식 사진"
                    />
                  </button>
                  <button
                    className="calendar-photo-box"
                    type="button"
                    onClick={() =>
                      {
                      setPhotoZoom(1);
                      setPhotoPosition({ x: 0, y: 0 });
                      setExpandedPhoto({
                        src: "/inspection-images/camera1_label_20260507_011413_1.jpg",
                        alt: "라벨 사진",
                      });
                    }
                    }
                  >
                    <img
                      src="/inspection-images/camera1_label_20260507_011413_1.jpg"
                      alt="라벨 사진"
                    />
                  </button>
                </div>
              </div>

              <div className="table-section monthly-result-section">
                <div className="date-filter">
                  <select
                    value={filterStartYear}
                    onChange={(event) => {
                      setFilterStartYear(Number(event.target.value));
                    }}
                  >
                    {yearOptions.map((year) => (
                      <option value={year} key={`start-year-${year}`}>{year}년</option>
                    ))}
                  </select>
                  <select
                    value={filterStartMonth}
                    onChange={(event) => {
                      setFilterStartMonth(Number(event.target.value));
                    }}
                  >
                    {monthOptions.map((month) => (
                      <option value={month} key={`start-month-${month}`}>{month}월</option>
                    ))}
                  </select>
                  <select
                    value={filterStartDay}
                    onChange={(event) => {
                      setFilterStartDay(Number(event.target.value));
                    }}
                  >
                    {startDayOptions.map((day) => (
                      <option value={day} key={`start-day-${day}`}>{day}일</option>
                    ))}
                  </select>
                  <span>~</span>
                  <select
                    value={filterEndYear}
                    onChange={(event) => {
                      setFilterEndYear(Number(event.target.value));
                    }}
                  >
                    {yearOptions.map((year) => (
                      <option value={year} key={`end-year-${year}`}>{year}년</option>
                    ))}
                  </select>
                  <select
                    value={filterEndMonth}
                    onChange={(event) => {
                      setFilterEndMonth(Number(event.target.value));
                    }}
                  >
                    {monthOptions.map((month) => (
                      <option value={month} key={`end-month-${month}`}>{month}월</option>
                    ))}
                  </select>
                  <select
                    value={filterEndDay}
                    onChange={(event) => {
                      setFilterEndDay(Number(event.target.value));
                    }}
                  >
                    {endDayOptions.map((day) => (
                      <option value={day} key={`end-day-${day}`}>{day}일</option>
                    ))}
                  </select>
                  <select
                    value={filterExtinguisher}
                    onChange={(event) => setFilterExtinguisher(event.target.value)}
                  >
                    <option value="all">전체 ID</option>
                    <option value="1">ID:1</option>
                    <option value="2">ID:2</option>
                    <option value="3">ID:3</option>
                  </select>
                  <button
                    className="date-filter-apply"
                    type="button"
                    onClick={() => {
                      setAppliedFilter({
                        startDate: filterStartDate,
                        endDate: filterEndDate,
                        extinguisher: filterExtinguisher,
                      });
                      setSelectedPhotoRecordId("");
                    }}
                  >
                    적용
                  </button>
                </div>
                <h2>검사 결과</h2>

                <div className="inspection-table-scroll">
                  <table className="inspection-table">
                    <colgroup>
                      <col className="inspection-col-no" />
                      <col className="inspection-col-id" />
                      <col className="inspection-col-location" />
                      <col className="inspection-col-pressure" />
                      <col className="inspection-col-appearance" />
                      <col className="inspection-col-expiry" />
                      <col className="inspection-col-result" />
                      <col className="inspection-col-time" />
                    </colgroup>
                    <thead>
                      <tr>
                        <th>No</th>
                        <th>소화기 ID</th>
                        <th>위치</th>
                        <th>압력</th>
                        <th>외관</th>
                        <th>내용연한</th>
                        <th>결과</th>
                        <th>시간</th>
                      </tr>
                    </thead>
                    <tbody>
                      {filteredRecords.map((item, index) => (
                        <tr key={item.id}>
                          <td>{index + 1}</td>
                          <td>
                            <button
                              className="inspection-id-button"
                              type="button"
                              onClick={() => setSelectedPhotoRecordId(item.id)}
                            >
                              {getExtinguisherName(item, index)}
                            </button>
                          </td>
                          <td>B1F</td>
                          <td>{item.pressure === "normal" ? "정상" : "낮음"}</td>
                          <td>{item.appearance === "clean" ? "양호" : "오염"}</td>
                          <td>{item.expiry || "2028:05"}</td>
                          <td
                            className={
                              item.result === "pass"
                                ? "result-pass"
                                : "result-fail"
                            }
                          >
                            {item.result === "pass" ? "합격" : "불합격"}
                          </td>
                          <td>{formatInspectionTime(item)}</td>
                        </tr>
                      ))}
                      {filteredRecords.length === 0 && (
                        <tr>
                          <td colSpan="8">선택한 기간에 검사 기록이 없습니다.</td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          </div>
        );

      default:
        return null;
    }
  };

  return (
    <div className="container">
      <h1> 🧯 소화기 점검 시스템 🧯</h1>

      <div className="content-row">
        <div className="map-section">
          <h2>B1F 맵</h2>
          <img src="/B1F.jpg" alt="B1F Map" className="map-image" />
        </div>

        <div className="right-section">
          <div className="extra-section">
            <div className="tab-header">
              <button
                className={`tab-button ${activeTab === "home" ? "active" : ""}`}
                onClick={() => setActiveTab("home")}
              >
                Home
              </button>

              <button
                className={`tab-button ${activeTab === "calendar" ? "active" : ""}`}
                onClick={() => setActiveTab("calendar")}
              >
                월간 검사 현황
              </button>

              <button
                className={`tab-button ${activeTab === "hardware" ? "active" : ""}`}
                onClick={() => setActiveTab("hardware")}
              >
                Hardware
              </button>
            </div>

            <div className="tab-body">{renderTabContent()}</div>
          </div>

        </div>
      </div>
      {expandedPhoto && (
        <div className="photo-modal-backdrop" onClick={() => setExpandedPhoto(null)}>
          <div
            className="photo-modal"
            ref={photoModalRef}
            onClick={(event) => event.stopPropagation()}
            onMouseMove={(event) => {
              if (!photoDrag) {
                return;
              }

              setPhotoPosition({
                x: event.clientX - photoDrag.startX,
                y: event.clientY - photoDrag.startY,
              });
            }}
            onMouseUp={() => setPhotoDrag(null)}
            onMouseLeave={() => setPhotoDrag(null)}
            onWheel={(event) => {
              event.preventDefault();
              setPhotoZoom((zoom) => {
                const nextZoom = event.deltaY < 0 ? zoom + 0.15 : zoom - 0.15;
                return Math.min(3, Math.max(0.5, nextZoom));
              });
            }}
          >
            <div className="photo-modal-controls">
              <button
                className="photo-modal-control"
                type="button"
                aria-label="전체화면 종료"
                onClick={() => {
                  if (document.fullscreenElement) {
                    document.exitFullscreen();
                  }
                }}
              >
                -
              </button>
              <button
                className="photo-modal-control photo-modal-fullscreen"
                type="button"
                aria-label="전체화면"
                onClick={() => {
                  if (document.fullscreenElement) {
                    document.exitFullscreen();
                    return;
                  }

                  photoModalRef.current?.requestFullscreen();
                }}
              />
            </div>
            <button
              className="photo-modal-close"
              type="button"
              aria-label="확대 사진 닫기"
              onClick={() => setExpandedPhoto(null)}
            />
            <img
              src={expandedPhoto.src}
              alt={expandedPhoto.alt}
              className={photoDrag ? "dragging" : ""}
              onMouseDown={(event) => {
                event.preventDefault();
                setPhotoDrag({
                  startX: event.clientX - photoPosition.x,
                  startY: event.clientY - photoPosition.y,
                });
              }}
              style={{
                transform: `translate(${photoPosition.x}px, ${photoPosition.y}px) scale(${photoZoom})`,
              }}
            />
          </div>
        </div>
      )}
    </div>
  );
}

export default App;
