import { useCallback, useEffect, useRef, useState } from "react";
import { collection, onSnapshot, query, orderBy } from "firebase/firestore";
import { db } from "./firebase";
import "./App.css";

const getStoredRegularInspectionSchedule = () => {
  if (typeof window === "undefined") {
    return null;
  }

  try {
    const savedSchedule = window.localStorage.getItem("regularInspectionSchedule");
    return savedSchedule ? JSON.parse(savedSchedule) : null;
  } catch (error) {
    return null;
  }
};

const defaultBringupLogGroups = [
  { id: "tetra", title: "TETRA / 모터", lines: [] },
  { id: "lidar", title: "LiDAR", lines: [] },
  { id: "nav2", title: "Nav2 / Localization", lines: [] },
  { id: "rviz", title: "RViz", lines: [] },
  { id: "realsense", title: "RealSense", lines: [] },
  { id: "apriltag_servo", title: "AprilTag Servo", lines: [] },
];
const regularInspectionLastRunKey = "regularInspectionLastRunKey";
const localInspectionResultsPath = "/local-inspection-results.json";

const getInspectionRecordKey = (item) => (
  item.id || `${item.extinguisher_id || "unknown"}-${item.run_id || item.time || ""}`
);

const mergeInspectionRecords = (firebaseRecords, localRecords) => {
  const recordsByKey = new Map();

  [...localRecords, ...firebaseRecords].forEach((item) => {
    recordsByKey.set(getInspectionRecordKey(item), item);
  });

  return Array.from(recordsByKey.values()).sort((a, b) => {
    const aTime = new Date(a.time || 0).getTime() || 0;
    const bTime = new Date(b.time || 0).getTime() || 0;
    return bTime - aTime;
  });
};

function App() {
  const streamHost = window.location.hostname || "localhost";
  const inspectionStreamBaseUrl = `http://${streamHost}:8000`;
  const apriltagStreamBaseUrl = `http://${streamHost}:8001`;
  const hardwareControlBaseUrl = `http://${streamHost}:8002`;
  const robotPoseBaseUrl = `http://${streamHost}:8003`;
  const [firebaseData, setFirebaseData] = useState([]);
  const [localData, setLocalData] = useState([]);
  const [activeTab, setActiveTab] = useState("home");
  const [activeMapView, setActiveMapView] = useState("b1f");
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
  const [filterResult, setFilterResult] = useState("all");
  const [appliedFilter, setAppliedFilter] = useState(null);
  const [filterError, setFilterError] = useState("");
  const [isSchedulePanelOpen, setIsSchedulePanelOpen] = useState(false);
  const [regularInspectionSchedule, setRegularInspectionSchedule] = useState(
    () => getStoredRegularInspectionSchedule()
  );
  const [scheduleDay, setScheduleDay] = useState(
    () => getStoredRegularInspectionSchedule()?.day || today.getDate()
  );
  const [scheduleTime, setScheduleTime] = useState(
    () => getStoredRegularInspectionSchedule()?.time || "09:00"
  );
  const [selectedPhotoRecordId, setSelectedPhotoRecordId] = useState("");
  const [selectedPhotoRecordSnapshot, setSelectedPhotoRecordSnapshot] = useState(null);
  const [expandedPhoto, setExpandedPhoto] = useState(null);
  const [photoZoom, setPhotoZoom] = useState(1);
  const [photoPosition, setPhotoPosition] = useState({ x: 0, y: 0 });
  const [photoDrag, setPhotoDrag] = useState(null);
  const [streamRetryKey, setStreamRetryKey] = useState(Date.now());
  const [neopixelValues, setNeopixelValues] = useState({
    internal: 0,
    external: 0,
  });
  const [hardwareConnected, setHardwareConnected] = useState({
    ballscrew: false,
    st3235: false,
    neopixel: false,
    tetraMotor: false,
    lidar: false,
  });
  const [inspectionRunning, setInspectionRunning] = useState(false);
  const [missionLogs, setMissionLogs] = useState([]);
  const [bringupLogGroups, setBringupLogGroups] = useState(defaultBringupLogGroups);
  const [emergencyStopActive, setEmergencyStopActive] = useState(false);
  const [liveConnected, setLiveConnected] = useState({
    apriltag: false,
    camera1: false,
    camera2: false,
  });
  const [robotPose, setRobotPose] = useState(null);
  const [liveMapLoaded, setLiveMapLoaded] = useState(false);
  const [liveMapRetryKey, setLiveMapRetryKey] = useState(Date.now());
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
  const scheduleDayOptions = Array.from({ length: 31 }, (_, index) => index + 1);
  const startDayOptions = Array.from(
    { length: new Date(filterStartYear, filterStartMonth, 0).getDate() },
    (_, index) => index + 1
  );
  const endDayOptions = Array.from(
    { length: new Date(filterEndYear, filterEndMonth, 0).getDate() },
    (_, index) => index + 1
  );
  const data = mergeInspectionRecords(firebaseData, localData);

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

  const saveRegularInspectionSchedule = () => {
    if (inspectionRunning) {
      return;
    }

    const schedule = {
      day: Number(scheduleDay),
      time: scheduleTime,
    };

    setRegularInspectionSchedule(schedule);
    window.localStorage.setItem("regularInspectionSchedule", JSON.stringify(schedule));
    window.localStorage.removeItem(regularInspectionLastRunKey);
    setIsSchedulePanelOpen(false);
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
    const inResultRange =
      appliedFilter.result === "all" ||
      (appliedFilter.result === "pass" && item.result === "pass") ||
      (appliedFilter.result === "fail" && item.result !== "pass");

    return inDateRange && inExtinguisherRange && inResultRange;
  });

  const selectedPhotoRecord =
    filteredRecords.find((item) => item.id === selectedPhotoRecordId) ||
    (selectedPhotoRecordSnapshot?.id === selectedPhotoRecordId ? selectedPhotoRecordSnapshot : null);
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

  const resolveInspectionImageUrl = (src) => {
    if (!src) {
      return "";
    }

    if (/^(https?:)?\/\//i.test(src) || src.startsWith("data:") || src.startsWith("blob:")) {
      return src;
    }

    return src.startsWith("/") ? src : `/${src}`;
  };

  const getInspectionPhotoItems = (item) => {
    if (!item) {
      return [];
    }

    const photos = [];
    if (item.pressure_image) {
      photos.push({ label: "압력 게이지", src: resolveInspectionImageUrl(item.pressure_image) });
    }
    if (item.expiry_image) {
      photos.push({ label: "라벨", src: resolveInspectionImageUrl(item.expiry_image) });
    }

    getAppearanceImageUrls(item).forEach((src, index) => {
      photos.push({ label: `부식 ${index + 1}면`, src: resolveInspectionImageUrl(src) });
    });

    if (item.full_image) {
      photos.push({ label: "전체 사진", src: resolveInspectionImageUrl(item.full_image) });
    }

    return photos;
  };

  const selectPhotoRecord = (item) => {
    setSelectedPhotoRecordId(item.id);
    setSelectedPhotoRecordSnapshot(item);
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

  const isRobotPoseAvailable = Boolean(robotPose?.available);
  const isLiveMapReady = liveMapLoaded;
  const robotMarkerStyle = isRobotPoseAvailable
    ? {
        left: `${Math.max(0, Math.min(100, robotPose.display_percent_x ?? robotPose.percent_x))}%`,
        top: `${Math.max(0, Math.min(100, robotPose.display_percent_y ?? robotPose.percent_y))}%`,
        transform: `translate(-50%, -50%) rotate(${robotPose.display_yaw ?? Math.PI / 2 - (robotPose.yaw || 0)}rad)`,
      }
    : {};

  const formatRobotPose = () => {
    if (!isRobotPoseAvailable) {
      return "위치 수신 대기";
    }

    return `x ${robotPose.x.toFixed(2)} / y ${robotPose.y.toFixed(2)}`;
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
    if (inspectionRunning) {
      return;
    }

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

  const setEmergencyMotorStop = async (active) => {
    setEmergencyStopActive(active);
    try {
      await fetch(`${robotPoseBaseUrl}/motor_stop`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ active }),
      });
    } catch (error) {
      console.error("Emergency motor stop request failed:", error);
    }
  };

  const toggleEmergencyMotorStop = () => {
    setEmergencyMotorStop(!emergencyStopActive);
  };

  const startInspectionMission = useCallback(async () => {
    if (inspectionRunning) {
      return;
    }

    try {
      await fetch(`${robotPoseBaseUrl}/mission/start`, {
        method: "POST",
      });
    } catch (error) {
      console.error("Mission start request failed:", error);
    }
  }, [inspectionRunning, robotPoseBaseUrl]);

  const renderConnectionStatus = (connected) => (
    <div className={`connection-row ${connected ? "connection-row-connected" : ""}`}>
      <span className={`connection-dot ${connected ? "connection-dot-connected" : ""}`} />
      <span>{connected ? "연결 완료" : "연결 안됨"}</span>
    </div>
  );

  useEffect(() => {
    if (!regularInspectionSchedule) {
      return undefined;
    }

    const checkRegularInspectionSchedule = () => {
      if (inspectionRunning) {
        return;
      }

      const now = new Date();
      const currentTime = `${String(now.getHours()).padStart(2, "0")}:${String(now.getMinutes()).padStart(2, "0")}`;
      if (now.getDate() !== Number(regularInspectionSchedule.day) || currentTime !== regularInspectionSchedule.time) {
        return;
      }

      const runKey = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-${String(now.getDate()).padStart(2, "0")} ${regularInspectionSchedule.time}`;
      if (window.localStorage.getItem(regularInspectionLastRunKey) === runKey) {
        return;
      }

      window.localStorage.setItem(regularInspectionLastRunKey, runKey);
      startInspectionMission();
    };

    checkRegularInspectionSchedule();
    const intervalId = setInterval(checkRegularInspectionSchedule, 1000);
    return () => clearInterval(intervalId);
  }, [regularInspectionSchedule, inspectionRunning, startInspectionMission]);

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
          setInspectionRunning(Boolean(payload.led_locked || payload.inspection?.running));
          setMissionLogs(Array.isArray(payload.inspection?.logs) ? payload.inspection.logs : []);
          setHardwareConnected({
            ballscrew: Boolean(payload.hardware?.ballscrew),
            st3235: Boolean(payload.hardware?.st3235),
            neopixel: Boolean(payload.hardware?.neopixel),
            tetraMotor: Boolean(payload.hardware?.tetra_motor),
            lidar: Boolean(payload.hardware?.lidar),
          });
          setNeopixelValues({
            internal: Number(payload.state.internal || 0),
            external: Number(payload.state.external || 0),
          });
        }
      } catch (error) {
        console.error("NeoPixel state load failed:", error);
        if (isMounted) {
          setHardwareConnected({
            ballscrew: false,
            st3235: false,
            neopixel: false,
            tetraMotor: false,
            lidar: false,
          });
        }
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

        setFirebaseData(result);
        setSelectedPhotoRecordId((selectedId) => {
          if (!selectedId) {
            return selectedId;
          }

          const updatedSelectedRecord = result.find((item) => item.id === selectedId);
          if (updatedSelectedRecord) {
            setSelectedPhotoRecordSnapshot(updatedSelectedRecord);
            return selectedId;
          }

          setSelectedPhotoRecordSnapshot(null);
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
    let isMounted = true;

    const loadLocalInspectionResults = async () => {
      try {
        const response = await fetch(`${localInspectionResultsPath}?t=${Date.now()}`, {
          cache: "no-store",
        });
        if (!response.ok) {
          return;
        }

        const records = await response.json();
        if (isMounted && Array.isArray(records)) {
          setLocalData(records);
        }
      } catch (error) {
        // Firebase remains the primary live source; local JSON is a best-effort fallback.
      }
    };

    loadLocalInspectionResults();
    const intervalId = setInterval(loadLocalInspectionResults, 3000);

    return () => {
      isMounted = false;
      clearInterval(intervalId);
    };
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
          camera1: Boolean(health.camera1),
          camera2: Boolean(health.camera2),
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

  useEffect(() => {
    let isMounted = true;

    const loadRobotPose = async () => {
      try {
        const response = await fetch(`${robotPoseBaseUrl}/pose`, {
          cache: "no-store",
        });

        if (!response.ok) {
          throw new Error("robot pose request failed");
        }

        const pose = await response.json();
        if (isMounted) {
          setRobotPose(pose);
        }
      } catch (error) {
        if (isMounted) {
          setRobotPose({ available: false });
        }
      }
    };

    loadRobotPose();
    const intervalId = setInterval(loadRobotPose, 300);
    return () => {
      isMounted = false;
      clearInterval(intervalId);
    };
  }, [robotPoseBaseUrl]);

  useEffect(() => {
    let isMounted = true;

    const loadBringupLogs = async () => {
      try {
        const response = await fetch(`${robotPoseBaseUrl}/logs/bringup`, {
          cache: "no-store",
        });

        if (!response.ok) {
          throw new Error("bringup log request failed");
        }

        const payload = await response.json();
        if (isMounted && Array.isArray(payload.groups)) {
          setBringupLogGroups(payload.groups);
        }
      } catch (error) {
        if (isMounted) {
          setBringupLogGroups(defaultBringupLogGroups);
        }
      }
    };

    loadBringupLogs();
    const intervalId = setInterval(loadBringupLogs, 1000);
    return () => {
      isMounted = false;
      clearInterval(intervalId);
    };
  }, [robotPoseBaseUrl]);

  useEffect(() => {
    if (activeMapView !== "live" || liveMapLoaded) {
      return undefined;
    }

    const intervalId = setInterval(() => {
      setLiveMapRetryKey(Date.now());
    }, 1000);

    return () => clearInterval(intervalId);
  }, [activeMapView, liveMapLoaded]);

  const renderTabContent = () => {
    switch (activeTab) {
      case "home":
        return (
          <div className="tab-content home-dashboard">
            <div className="home-live-area">
              <div className="section-title-row">
                <h2>Live Monitoring</h2>
                <span className={`system-status ${inspectionRunning ? "system-status-running" : ""}`}>
                  {inspectionRunning ? "검사 진행 중" : "Standby"}
                </span>
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
                  {missionLogs.length > 0 ? (
                    missionLogs.slice(-12).map((log, index) => (
                      <div key={`${log.time || "log"}-${index}`}>
                        [{log.time || "--:--:--"}] {log.message}
                      </div>
                    ))
                  ) : (
                    <div>[--:--:--] 작업 대기 중</div>
                  )}
                </div>
              </div>
            </div>

            <aside className="home-command-panel">
              <div className="command-group">
                <div className="command-group-title">검사 · 복귀</div>
                <div className="command-button-stack">
                  <button
                    className="primary-action"
                    type="button"
                    disabled={inspectionRunning}
                    onClick={startInspectionMission}
                  >
                    {inspectionRunning ? "검사 진행 중" : "검사 실행"}
                  </button>
                </div>
              </div>

              <div className="command-group schedule-command-group">
                <div className="command-group-title">정기 검사 예약</div>
                <div className="schedule-command-body">
                  <button
                    className="schedule-toggle-button"
                    type="button"
                    disabled={inspectionRunning}
                    onClick={() => {
                      if (inspectionRunning) {
                        return;
                      }
                      setIsSchedulePanelOpen((isOpen) => !isOpen);
                    }}
                  >
                    정기검사예약
                  </button>
                  <div className="schedule-status">
                    {regularInspectionSchedule
                      ? `매월 ${regularInspectionSchedule.day}일 ${regularInspectionSchedule.time}`
                      : "예약 없음"}
                  </div>
                  {inspectionRunning && <small className="schedule-lock-message">검사 중 예약 변경 잠김</small>}
                  {isSchedulePanelOpen && (
                    <div className={`schedule-controls ${inspectionRunning ? "schedule-controls-locked" : ""}`}>
                      <label>
                        <span>매월</span>
                        <select
                          value={scheduleDay}
                          disabled={inspectionRunning}
                          onChange={(event) => setScheduleDay(Number(event.target.value))}
                        >
                          {scheduleDayOptions.map((day) => (
                            <option value={day} key={`schedule-day-${day}`}>
                              {day}일
                            </option>
                          ))}
                        </select>
                      </label>
                      <label>
                        <span>시간</span>
                        <input
                          type="time"
                          value={scheduleTime}
                          disabled={inspectionRunning}
                          onChange={(event) => setScheduleTime(event.target.value)}
                        />
                      </label>
                      <button
                        className="schedule-save-button"
                        type="button"
                        disabled={inspectionRunning}
                        onClick={saveRegularInspectionSchedule}
                      >
                        예약 저장
                      </button>
                    </div>
                  )}
                </div>
              </div>

              <button
                className={`emergency-stop-button ${emergencyStopActive ? "emergency-stop-button-active" : ""}`}
                type="button"
                aria-pressed={emergencyStopActive}
                onClick={toggleEmergencyMotorStop}
                onContextMenu={(event) => event.preventDefault()}
              >
                <span className="emergency-stop-icon" />
                <span>{emergencyStopActive ? "MOTOR" : "EMERGENCY"}</span>
                <span>{emergencyStopActive ? "STOPPED" : "STOP"}</span>
              </button>
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
                <span>테트라 모터</span>
                {renderConnectionStatus(hardwareConnected.tetraMotor)}
              </div>
              <div className="hardware-status-card">
                <span>LiDAR</span>
                {renderConnectionStatus(hardwareConnected.lidar)}
              </div>
              <div className="hardware-status-card">
                <span>상하 이동 모듈</span>
                {renderConnectionStatus(hardwareConnected.ballscrew)}
              </div>
              <div className="hardware-status-card">
                <span>소화기 회전 모듈</span>
                {renderConnectionStatus(hardwareConnected.st3235)}
              </div>
              <div className="hardware-status-card">
                <span>소화기 검사 카메라 Top</span>
                {renderConnectionStatus(liveConnected.camera1)}
              </div>
              <div className="hardware-status-card">
                <span>소화기 검사 카메라 Bottom</span>
                {renderConnectionStatus(liveConnected.camera2)}
              </div>
              <div className="hardware-status-card">
                <span>자동정렬 카메라</span>
                {renderConnectionStatus(liveConnected.apriltag)}
              </div>
              <div className="hardware-status-card">
                <span>NeoPixel LED</span>
                {renderConnectionStatus(hardwareConnected.neopixel)}
              </div>
              <div className="hardware-section-divider" />
              <div className="hardware-status-card">
                <span>LED(소화기 내부)</span>
                <div className={`neopixel-control ${inspectionRunning ? "neopixel-control-locked" : ""}`}>
                  <input
                    className="neopixel-slider"
                    type="range"
                    min="0"
                    max="255"
                    value={neopixelValues.internal}
                    disabled={inspectionRunning}
                    onChange={(event) => setNeopixelBrightness("internal", event.target.value)}
                  />
                  <span>{neopixelValues.internal}</span>
                </div>
                {inspectionRunning && <small className="neopixel-lock-message">검사 중 LED 조정 잠김</small>}
              </div>
              <div className="hardware-status-card">
                <span>LED(소화기 외부)</span>
                <div className={`neopixel-control ${inspectionRunning ? "neopixel-control-locked" : ""}`}>
                  <input
                    className="neopixel-slider"
                    type="range"
                    min="0"
                    max="255"
                    value={neopixelValues.external}
                    disabled={inspectionRunning}
                    onChange={(event) => setNeopixelBrightness("external", event.target.value)}
                  />
                  <span>{neopixelValues.external}</span>
                </div>
                {inspectionRunning && <small className="neopixel-lock-message">검사 중 LED 조정 잠김</small>}
              </div>
            </div>
          </div>
        );

      case "log":
        return (
          <div className="tab-content">
            <div className="bringup-log-grid">
              {bringupLogGroups.map((group) => (
                <section className="bringup-log-card" key={group.id}>
                  <div className="bringup-log-title">{group.title}</div>
                  <div className="full-log-panel">
                    {group.lines?.length > 0 ? (
                      group.lines.map((line, index) => (
                        <div className="bringup-log-line" key={`${group.id}-${index}`}>
                          {line}
                        </div>
                      ))
                    ) : (
                      <div className="bringup-log-line muted">로그 없음</div>
                    )}
                  </div>
                </section>
              ))}
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
                  <select
                    value={filterResult}
                    onChange={(event) => setFilterResult(event.target.value)}
                  >
                    <option value="all">전체 결과</option>
                    <option value="pass">합격</option>
                    <option value="fail">불합격</option>
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
                        result: filterResult,
                      });
                      setFilterError("");
                      setSelectedPhotoRecordId("");
                      setSelectedPhotoRecordSnapshot(null);
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
                              onClick={() => selectPhotoRecord(item)}
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
          <div className="map-button-row">
            <button
              className={`map-view-button ${activeMapView === "b1f" ? "active" : ""}`}
              type="button"
              onClick={() => setActiveMapView("b1f")}
            >
              B1F
            </button>
            <button
              className={`map-view-button ${activeMapView === "live" ? "active" : ""}`}
              type="button"
              onClick={() => setActiveMapView("live")}
            >
              Live map
            </button>
          </div>
          <div className={`map-image-frame ${activeMapView === "live" ? "map-image-frame-live" : ""}`}>
            <img
              src={
                activeMapView === "live"
                  ? `${robotPoseBaseUrl}/map.png?t=${liveMapRetryKey}`
                  : "/B1F.jpg"
              }
              alt={activeMapView === "live" ? "Live map" : "B1F Map"}
              className={`map-image ${activeMapView === "live" ? "map-image-live" : ""} ${
                activeMapView === "live" && !isLiveMapReady ? "map-image-loading" : ""
              }`}
              onLoad={() => {
                if (activeMapView === "live") {
                  setLiveMapLoaded(true);
                }
              }}
              onError={() => {
                if (activeMapView === "live") {
                  setLiveMapLoaded(false);
                }
              }}
            />
            {activeMapView === "live" && !isLiveMapReady && (
              <div className="live-map-placeholder">
                <div className="live-map-loader" />
                <strong>Live map 연결 대기</strong>
                <span>맵 서버 신호를 확인하는 중</span>
              </div>
            )}
            {activeMapView === "live" && isRobotPoseAvailable && (
              <span
                className="map-robot-marker"
                style={robotMarkerStyle}
                aria-label="실시간 로봇 위치"
              />
            )}
            {activeMapView === "live" && (
              <div className="map-pose-status">
                <span className={isRobotPoseAvailable ? "pose-online" : "pose-offline"} />
                {formatRobotPose()}
              </div>
            )}
          </div>
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

              <button
                className={`tab-button ${activeTab === "log" ? "active" : ""}`}
                onClick={() => setActiveTab("log")}
              >
                Log
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
