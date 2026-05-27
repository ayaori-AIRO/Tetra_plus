import { useEffect, useRef, useState } from "react";
import { collection, onSnapshot, query, orderBy } from "firebase/firestore";
import { db } from "./firebase";
import "./App.css";

function App() {
  const streamHost = window.location.hostname || "localhost";
  const inspectionStreamBaseUrl = `http://${streamHost}:8000`;
  const apriltagStreamBaseUrl = `http://${streamHost}:8001`;
  const hardwareControlBaseUrl = `http://${streamHost}:8002`;
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
  const [filterError, setFilterError] = useState("");
  const [selectedPhotoRecordId, setSelectedPhotoRecordId] = useState("");
  const [expandedPhoto, setExpandedPhoto] = useState(null);
  const [photoZoom, setPhotoZoom] = useState(1);
  const [photoPosition, setPhotoPosition] = useState({ x: 0, y: 0 });
  const [photoDrag, setPhotoDrag] = useState(null);
  const [streamRetryKey, setStreamRetryKey] = useState(Date.now());
  const [neopixelValues, setNeopixelValues] = useState({
    internal: 0,
    external: 0,
  });
  const [liveConnected, setLiveConnected] = useState({
    apriltag: false,
    camera1: false,
    camera2: false,
  });
  const photoModalRef = useRef(null);
  const streamRetryTimerRef = useRef(null);
  const neopixelTimersRef = useRef({});
  const extinguisherNames = [
    "EXT1 (B1F 복도 A)",
    "EXT2 B1F 복도B",
    "EXT3 B1F 비상구 앞",
  ];

  const filterStartDate = new Date(filterStartYear, filterStartMonth - 1, filterStartDay);
  const filterEndDate = new Date(filterEndYear, filterEndMonth - 1, filterEndDay, 23, 59, 59);
  const isFilterDateRangeInvalid = filterStartDate > filterEndDate;
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

  const getExtinguisherName = (item, index) => {
    const match = String(item.extinguisher_id || "").match(/(?:id|ext)([1-3])/i);
    if (match) {
      return extinguisherNames[Number(match[1]) - 1];
    }
    return item.extinguisher_id || extinguisherNames[index % 3];
  };

  const getPressureText = (item) => {
    if (item.pressure === "normal") {
      return "정상";
    }
    if (item.pressure === "low") {
      return "낮음";
    }
    if (item.pressure === "인식 안됨") {
      return "인식 안됨";
    }
    return item.pressure || "판정불가";
  };

  const getAppearanceText = (item) => {
    if (item.appearance === "clean") {
      return "정상";
    }
    if (item.appearance === "dirty") {
      return "부식";
    }
    if (item.appearance === "인식 안됨") {
      return "인식 안됨";
    }
    return item.appearance || "판정불가";
  };

  const filteredRecords = data.filter((item, index) => {
    if (!appliedFilter) {
      return true;
    }

    const itemTime = getItemTime(item);
    const inDateRange = !itemTime || (itemTime >= appliedFilter.startDate && itemTime <= appliedFilter.endDate);
    const match = String(item.extinguisher_id || "").match(/(?:id|ext)([1-3])/i);
    const itemExtinguisherNumber = match ? Number(match[1]) : (index % 3) + 1;
    const inExtinguisherRange =
      appliedFilter.extinguisher === "all" || itemExtinguisherNumber === Number(appliedFilter.extinguisher);

    return inDateRange && inExtinguisherRange;
  });

  const selectedPhotoRecord = filteredRecords.find((item) => item.id === selectedPhotoRecordId);
  const dateFilterMessage = isFilterDateRangeInvalid
    ? "시작일은 종료일보다 늦을 수 없습니다."
    : filterError;

  const getAppearanceImageUrls = (item) => {
    if (!item) {
      return [];
    }

    if (Array.isArray(item.appearance_images) && item.appearance_images.length > 0) {
      return item.appearance_images.filter(Boolean);
    }

    if (Array.isArray(item.appearance_sides) && item.appearance_sides.length > 0) {
      return item.appearance_sides.map((side) => side.image).filter(Boolean);
    }

    return item.appearance_image ? [item.appearance_image] : [];
  };

  const getInspectionPhotoItems = (item) => {
    if (!item) {
      return [];
    }

    const photos = [];
    if (item.pressure_image) {
      photos.push({ label: "압력 게이지", src: item.pressure_image });
    }
    if (item.expiry_image) {
      photos.push({ label: "라벨", src: item.expiry_image });
    }

    getAppearanceImageUrls(item).forEach((src, index) => {
      photos.push({ label: `부식 ${index + 1}면`, src });
    });

    if (item.full_image) {
      photos.push({ label: "전체 사진", src: item.full_image });
    }

    return photos;
  };

  const openExpandedPhoto = (photo) => {
    setPhotoZoom(1);
    setPhotoPosition({ x: 0, y: 0 });
    setExpandedPhoto({
      src: photo.src,
      alt: photo.label,
    });
  };

  const retryLiveStream = (cameraName) => {
    setLiveConnected((prev) => ({
      ...prev,
      [cameraName]: false,
    }));

    if (streamRetryTimerRef.current) {
      return;
    }

    streamRetryTimerRef.current = setTimeout(() => {
      streamRetryTimerRef.current = null;
      setStreamRetryKey(Date.now());
    }, 1000);
  };

  const markLiveStreamConnected = (cameraName) => {
    setLiveConnected((prev) => ({
      ...prev,
      [cameraName]: true,
    }));
  };

  const refreshLiveStreams = () => {
    if (streamRetryTimerRef.current) {
      return;
    }

    streamRetryTimerRef.current = setTimeout(() => {
      streamRetryTimerRef.current = null;
      setStreamRetryKey(Date.now());
    }, 300);
  };

  const setNeopixelBrightness = (target, value) => {
    const brightness = Math.max(0, Math.min(255, Number(value)));
    setNeopixelValues((prev) => ({
      ...prev,
      [target]: brightness,
    }));

    if (neopixelTimersRef.current[target]) {
      clearTimeout(neopixelTimersRef.current[target]);
    }

    neopixelTimersRef.current[target] = setTimeout(async () => {
      neopixelTimersRef.current[target] = null;
      try {
        await fetch(`${hardwareControlBaseUrl}/neopixel`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            target,
            value: brightness,
          }),
        });
      } catch (error) {
        console.error("NeoPixel brightness update failed:", error);
      }
    }, 250);
  };

  useEffect(() => {
    let isMounted = true;

    const loadNeopixelState = async () => {
      try {
        const response = await fetch(`${hardwareControlBaseUrl}/neopixel/state`, {
          cache: "no-store",
        });

        if (!response.ok) {
          throw new Error("NeoPixel state request failed");
        }

        const payload = await response.json();
        if (isMounted && payload.state) {
          setNeopixelValues({
            internal: Number(payload.state.internal || 0),
            external: Number(payload.state.external || 0),
          });
        }
      } catch (error) {
        console.error("NeoPixel state load failed:", error);
      }
    };

    loadNeopixelState();
    const intervalId = setInterval(loadNeopixelState, 1000);

    return () => {
      isMounted = false;
      clearInterval(intervalId);
    };
  }, [hardwareControlBaseUrl]);

  useEffect(() => {
    const q = query(
      collection(db, "inspection"),
      orderBy("time", "desc")
    );

    const unsubscribe = onSnapshot(
      q,
      (querySnapshot) => {
        const result = querySnapshot.docs.map((doc) => ({
          id: doc.id,
          ...doc.data(),
        }));

        setData(result);
        setSelectedPhotoRecordId((selectedId) => {
          if (!selectedId || result.some((item) => item.id === selectedId)) {
            return selectedId;
          }

          return "";
        });
      },
      (error) => {
        console.error("Inspection history realtime update failed:", error);
      }
    );

    return unsubscribe;
  }, []);

  useEffect(() => {
    const neopixelTimers = neopixelTimersRef.current;
    return () => {
      if (streamRetryTimerRef.current) {
        clearTimeout(streamRetryTimerRef.current);
      }
      Object.values(neopixelTimers).forEach((timerId) => {
        if (timerId) {
          clearTimeout(timerId);
        }
      });
    };
  }, []);

  useEffect(() => {
    const checkLiveHealth = async () => {
      try {
        const response = await fetch(`${inspectionStreamBaseUrl}/health`, {
          cache: "no-store",
        });

        if (!response.ok) {
          throw new Error("live health check failed");
        }

        const health = await response.json();
        setLiveConnected((prev) => ({
          ...prev,
          camera1: prev.camera1 && Boolean(health.camera1),
          camera2: prev.camera2 && Boolean(health.camera2),
        }));

        if (!health.camera1 || !health.camera2) {
          refreshLiveStreams();
        }
      } catch (error) {
        setLiveConnected((prev) => ({
          ...prev,
          camera1: false,
          camera2: false,
        }));
        refreshLiveStreams();
      }
    };

    checkLiveHealth();
    const intervalId = setInterval(checkLiveHealth, 1000);
    return () => clearInterval(intervalId);
  }, [inspectionStreamBaseUrl]);

  useEffect(() => {
    const checkAprilTagHealth = async () => {
      try {
        const response = await fetch(`${apriltagStreamBaseUrl}/health`, {
          cache: "no-store",
        });

        if (!response.ok) {
          throw new Error("apriltag stream health check failed");
        }

        const health = await response.json();
        const apriltagHealthy = Boolean(health.apriltag);
        setLiveConnected((prev) => {
          if (apriltagHealthy && !prev.apriltag) {
            refreshLiveStreams();
          }

          return {
            ...prev,
            apriltag: apriltagHealthy,
          };
        });

        if (!apriltagHealthy) {
          refreshLiveStreams();
        }
      } catch (error) {
        setLiveConnected((prev) => ({
          ...prev,
          apriltag: false,
        }));
        refreshLiveStreams();
      }
    };

    checkAprilTagHealth();
    const intervalId = setInterval(checkAprilTagHealth, 1000);
    return () => clearInterval(intervalId);
  }, [apriltagStreamBaseUrl]);

  const renderTabContent = () => {
    switch (activeTab) {
      case "home":
        return (
          <div className="tab-content home-dashboard">
            <div className="home-live-area">
              <div className="section-title-row">
                <h2>Live Monitoring</h2>
                <span className="system-status">Standby</span>
              </div>
              <div className="home-live-content">
                <div className="live-grid">
                  <div className="live-camera-card">
                    <div className="live-camera-title">자동정렬 카메라</div>
                    <div className="live-view">
                      {!liveConnected.apriltag && <div>Not Connected</div>}
                      <img
                        className="live-stream"
                        src={`${apriltagStreamBaseUrl}/video/apriltag?t=${streamRetryKey}`}
                        onLoad={() => markLiveStreamConnected("apriltag")}
                        onError={() => retryLiveStream("apriltag")}
                        style={{ display: liveConnected.apriltag ? "block" : "none" }}
                        alt="소화기 자동정렬 카메라"
                      />
                    </div>
                  </div>
                  <div className="live-camera-card">
                    <div className="live-camera-title">검사 카메라 1</div>
                    <div className="live-view">
                      {!liveConnected.camera1 && <div>Not Connected</div>}
                      <img
                        className="live-stream"
                        src={`${inspectionStreamBaseUrl}/video/camera1?t=${streamRetryKey}`}
                        onLoad={() => markLiveStreamConnected("camera1")}
                        onError={() => retryLiveStream("camera1")}
                        style={{ display: liveConnected.camera1 ? "block" : "none" }}
                        alt="소화기 검사 카메라1"
                      />
                    </div>
                  </div>
                  <div className="live-camera-card">
                    <div className="live-camera-title">검사 카메라 2</div>
                    <div className="live-view">
                      {!liveConnected.camera2 && <div>Not Connected</div>}
                      <img
                        className="live-stream"
                        src={`${inspectionStreamBaseUrl}/video/camera2?t=${streamRetryKey}`}
                        onLoad={() => markLiveStreamConnected("camera2")}
                        onError={() => retryLiveStream("camera2")}
                        style={{ display: liveConnected.camera2 ? "block" : "none" }}
                        alt="소화기 검사 카메라2"
                      />
                    </div>
                  </div>
                </div>
                <div className="inspection-log-panel">
                  <div>[22:45:01] EXT1 이동 시작</div>
                  <div>[22:45:08] 카메라 촬영 완료</div>
                  <div>[22:45:10] 압력게이지 정상</div>
                  <div>[22:45:12] OCR 완료</div>
                  <div>[22:45:15] 부식 없음</div>
                  <div>[22:45:16] 검사 종료</div>
                </div>
              </div>
            </div>

            <aside className="home-command-panel">
              <div className="command-group">
                <div className="command-group-title">개별 검사</div>
                <div className="command-button-stack">
                  <button type="button">EXT1</button>
                  <button type="button">EXT2</button>
                  <button type="button">EXT3</button>
                </div>
              </div>

              <div className="command-group">
                <div className="command-group-title">검사 · 복귀</div>
                <div className="command-button-stack">
                  <button className="secondary-action" type="button">홈 위치</button>
                  <button className="primary-action" type="button">검사 실행</button>
                </div>
              </div>
            </aside>
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
                <span>소화기 검사 카메라 Top</span>
                <div className="connection-row">
                  <span className="connection-dot"></span>
                  <span>연결 안됨</span>
                </div>
              </div>
              <div className="hardware-status-card">
                <span>소화기 검사 카메라 Bottom</span>
                <div className="connection-row">
                  <span className="connection-dot"></span>
                  <span>연결 안됨</span>
                </div>
              </div>
              <div className="hardware-status-card">
                <span>LED(소화기 내부)</span>
                <div className="neopixel-control">
                  <input
                    className="neopixel-slider"
                    type="range"
                    min="0"
                    max="255"
                    value={neopixelValues.internal}
                    onChange={(event) => setNeopixelBrightness("internal", event.target.value)}
                  />
                  <span>{neopixelValues.internal}</span>
                </div>
              </div>
              <div className="hardware-status-card">
                <span>LED(소화기 외부)</span>
                <div className="neopixel-control">
                  <input
                    className="neopixel-slider"
                    type="range"
                    min="0"
                    max="255"
                    value={neopixelValues.external}
                    onChange={(event) => setNeopixelBrightness("external", event.target.value)}
                  />
                  <span>{neopixelValues.external}</span>
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
                  {getInspectionPhotoItems(selectedPhotoRecord).map((photo) => (
                    <button
                      className="calendar-photo-box"
                      type="button"
                      key={`${photo.label}-${photo.src}`}
                      onClick={() => openExpandedPhoto(photo)}
                    >
                      <img src={photo.src} alt={photo.label} />
                      <span>{photo.label}</span>
                    </button>
                  ))}
                  {selectedPhotoRecord && getInspectionPhotoItems(selectedPhotoRecord).length === 0 && (
                    <div className="calendar-photo-empty">사진 없음</div>
                  )}
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
                    <option value="all">전체 EXT</option>
                    <option value="1">EXT1</option>
                    <option value="2">EXT2</option>
                    <option value="3">EXT3</option>
                  </select>
                  <button
                    className="date-filter-apply"
                    type="button"
                    disabled={isFilterDateRangeInvalid}
                    onClick={() => {
                      if (isFilterDateRangeInvalid) {
                        setFilterError("시작일은 종료일보다 늦을 수 없습니다.");
                        return;
                      }

                      setAppliedFilter({
                        startDate: filterStartDate,
                        endDate: filterEndDate,
                        extinguisher: filterExtinguisher,
                      });
                      setFilterError("");
                      setSelectedPhotoRecordId("");
                    }}
                  >
                    적용
                  </button>
                  {dateFilterMessage && (
                    <div className="date-filter-error" role="alert">
                      {dateFilterMessage}
                    </div>
                  )}
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
                          <td>{getPressureText(item)}</td>
                          <td>{getAppearanceText(item)}</td>
                          <td>{item.expiry || "판정불가"}</td>
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
      <h1>TETRA 소화기 점검 시스템</h1>

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
                Inspection History
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
