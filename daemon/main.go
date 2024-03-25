package main

import (
	"fmt"
	"log"
	"net"
	"net/http"
	"os"
	"strconv"
	"strings"
	"time"

	"github.com/gorilla/websocket"
	"github.com/pixelbender/go-traceroute/traceroute"
)

// SpeedMeasurement represents the speed measurement data structure
type SpeedMeasurement struct {
	SendTime          string  `json:"send_time"`
	ReceiveTime       string  `json:"receive_time"`
	TravelTime        float64 `json:"travel_time"`
	TransmissionSpeed float64 `json:"transmission_speed"`
	Route             string  `json:"route"`
}

var (
	ip   string
	port string
)

func main() {
	if len(os.Args) < 3 {
		fmt.Println(`Please provide at least two arguments.

Usage:     ./main <IP Address> <Port>
Example: ./main 127.0.0.1 8765`)
		os.Exit(1)
	}

	ip = os.Args[1]
	port = os.Args[2]

	if !isValidIP(ip) {
		fmt.Println("<IP Address> invalid.")
		os.Exit(1)
	}

	if !isValidPort(port) {
		fmt.Println("<Port> invalid.")
		os.Exit(1)
	}

	fmt.Println("IP Address:", ip)
	fmt.Println("Port:", port)
	ticker := time.NewTicker(12 * time.Hour)

	// Initialize WebSocket connection
	// TODO HACER QUE
	for {
		conn, _, err := websocket.DefaultDialer.Dial(fmt.Sprintf("ws://%s:%s", ip, port), nil)
		if err != nil {
			fmt.Println("Failed to connect:", err)
			time.Sleep(5 * time.Second) // Wait before attempting to reconnect
			continue
		}

		fmt.Println("Connected to", fmt.Sprintf("ws://%s:%s", ip, port))
		go handleWebSocket(conn)

		// getWebsites(conn)
		// send metrica velocidad
		sethostnamq(conn)
		handleq(conn)
		cancel := make(chan struct{})
		cancelsites := make(chan struct{})
		go func() {
			for {
				select {
				case <-ticker.C:
					fmt.Println("TIMEEEEE")
					handleq(conn)
				case <-cancel:
					return
				}
			}
		}()
		go func() {
			for {
				select {
				case <-ticker.C:
				case <-cancelsites:
					return
				}
			}
		}()
		// Wait for the connection to close before attempting to reconnect
		_, _, err = conn.ReadMessage()
		if err != nil {
			fmt.Println("Connection closed:", err)
		}

		// Close the connection
		_ = conn.Close()
		close(cancel)

		// Wait for 5 seconds before attempting to reconnect
		time.Sleep(5 * time.Second)
	}
}

// Function to check if IP address is valid
func isValidIP(ip string) bool {
	return net.ParseIP(ip) != nil
}

// Function to check if port is valid
func isValidPort(port string) bool {
	_, err := strconv.Atoi(port)
	return err == nil
}

func getWebsites(conn *websocket.Conn) {
	sendData := func(data interface{}) error {
		err := conn.WriteJSON(data)
		if err != nil {
			fmt.Println("Error sending data over WebSocket:", err)
		}
		return err
	}

	deskName, _ := os.Hostname()

	response := map[string]interface{}{
		"kind":      "getsites",
		"desk_name": deskName,
	}

	sendData(response)
}

func sethostnamq(conn *websocket.Conn) {
	// Function to send data over WebSocket connection
	sendData := func(data interface{}) error {
		err := conn.WriteJSON(data)
		if err != nil {
			fmt.Println("Error sending data over WebSocket:", err)
		}
		return err
	}

	deskName, _ := os.Hostname()

	response := map[string]interface{}{
		"kind":      "hostnameset",
		"desk_name": deskName,
	}
	sendData(response)
}

func handleq(conn *websocket.Conn) {
	// Function to send data over WebSocket connection
	sendData := func(data interface{}) error {
		err := conn.WriteJSON(data)
		if err != nil {
			fmt.Println("Error sending data over WebSocket:", err)
		}
		return err
	}

	speedMeasurement, err := ping()
	if err != nil {
		log.Println((err))
	}

	deskName, _ := os.Hostname()

	response := map[string]interface{}{
		"kind":      "load",
		"desk_name": deskName,
		"data":      speedMeasurement,
	}
	sendData(response)

}

func ping() (*SpeedMeasurement, error) {
	addr, err := net.ResolveIPAddr("ip4", ip)
	if err != nil {
		return nil, err
	}

	conn, err := net.DialIP("ip4:icmp", nil, addr)
	if err != nil {
		return nil, err
	}
	defer conn.Close()

	msg := make([]byte, 64)
	msg[0] = 8 // ICMP echo request type
	msg[1] = 0 // ICMP echo request code
	msg[2] = 0 // ICMP checksum (16 bits)

	// Set identifier and sequence number
	pid := os.Getpid() & 0xffff
	msg[4] = byte(pid >> 8)
	msg[5] = byte(pid & 0xff)

	// Calculate checksum
	checksum := checksum(msg)
	msg[2] = byte(checksum >> 8)
	msg[3] = byte(checksum & 0xff)

	// Send ICMP packet
	sendTime := time.Now()
	if _, err := conn.Write(msg); err != nil {
		return nil, err
	}

	// Wait for response
	conn.SetReadDeadline(time.Now().Add(3 * time.Second))
	receiveTime := time.Now()

	// Receive ICMP packet
	var buf [512]byte
	n, _, err := conn.ReadFrom(buf[0:])
	if err != nil {
		return nil, err
	}

	fmt.Println("Received response from", addr, "after", time.Since(receiveTime))

	// Calculate travel time and transmission speed
	travelTime := time.Since(receiveTime).Seconds()
	transmissionSpeed := travelTime / 2 // Assuming round trip, so divide by 2

	// Print ICMP packet data
	fmt.Printf("Received: % X\n", buf[:n])
	fmt.Printf("Travel Time: %.6f seconds\n", travelTime)
	fmt.Printf("Transmission Speed: %.6f seconds\n", transmissionSpeed)

	var finalreoutetext string
	hops, err := traceroute.Trace(net.ParseIP(ip))
	if err != nil {
		log.Fatal(err)
	}
	for _, h := range hops {
		for _, n := range h.Nodes {
			var formatted []string
			for _, duration := range n.RTT {
				formatted = append(formatted, fmt.Sprintf("%.6fs", duration.Seconds()))
			}

			formattedString := strings.Join(formatted, " ")
			println(formattedString)

			finalreoutetext += fmt.Sprintf("%d. <b>%v</b> <b>%v</b>\n", h.Distance, n.IP, formattedString)
		}
	}

	// Create SpeedMeasurement object
	speedMeasurement := SpeedMeasurement{
		SendTime:          sendTime.Format("2006-01-02 15:04:05.999999"),
		ReceiveTime:       receiveTime.Format("2006-01-02 15:04:05.999999"),
		TravelTime:        travelTime,
		TransmissionSpeed: transmissionSpeed,
		Route:             finalreoutetext,
	}

	return &speedMeasurement, nil
}

func checksum(msg []byte) uint16 {
	sum := 0
	for i := 0; i < len(msg)-1; i += 2 {
		sum += int(msg[i])*256 + int(msg[i+1])
	}
	if len(msg)%2 == 1 {
		sum += int(msg[len(msg)-1]) * 256
	}
	sum = (sum >> 16) + (sum & 0xffff)
	sum = sum + (sum >> 16)
	return uint16(^sum)
}

// Function to handle WebSocket communication
func handleWebSocket(conn *websocket.Conn) {
	defer conn.Close()

	// Function to send data over WebSocket connection
	sendData := func(data interface{}) error {
		err := conn.WriteJSON(data)
		if err != nil {
			fmt.Println("Error sending data over WebSocket:", err)
		}
		return err
	}

	// Function to receive data from WebSocket connection
	receiveData := func() (interface{}, error) {
		var data interface{}
		err := conn.ReadJSON(&data)
		if err != nil {
			// fmt.Println("Error receiving data from WebSocket:", err)
			return nil, err
		}
		return data, nil
	}

	// Function to check website availability
	checkWebsite := func(siteName string) bool {
		if !strings.HasPrefix(siteName, "http://") && !strings.HasPrefix(siteName, "https://") {
			siteName = "http://" + siteName
		}
		siteName = strings.TrimSuffix(siteName, "/")
		// Send HTTP GET request to the website
		resp, err := http.Get(siteName)
		if err != nil {
			// If there's an error, the website is considered unavailable
			return false
		}
		defer resp.Body.Close()

		// Check if the response status code indicates success (200 OK)
		return resp.StatusCode == http.StatusOK
	}

	// Main loop to handle WebSocket communication
	for {
		// Handle incoming messages
		data, err := receiveData()
		if err != nil {
			fmt.Println("Error receiving data from WebSocket:", err)
			break
		}

		// Parse incoming message
		message, ok := data.(map[string]interface{})
		if !ok {
			fmt.Println("Invalid message format received from WebSocket")
			continue
		}

		kind, exists := message["kind"].(string)
		if !exists {
			fmt.Println("Invalid message format: missing 'kind'")
			continue
		}

		// Handle different kinds of messages
		switch kind {
		case "whosthere":
			deskName, _ := os.Hostname()

			response := map[string]interface{}{
				"kind":            "status",
				"desk_name":       deskName,
				"message_chat_id": message["message_chat_id"],
			}
			sendData(response)
		case "status":
			deskName, _ := os.Hostname()

			deskNames, ok := message["desk_names"].([]interface{})
			if !ok {
				fmt.Println("Error: desk_names is not a slice")
				continue
			}

			for _, name := range deskNames {
				if name == deskName {
					response := map[string]interface{}{
						"kind":            "status",
						"desk_name":       deskName,
						"message_chat_id": message["message_chat_id"],
					}
					sendData(response)
				}
			}
		case "setsite":
		case "autosites":
			deskName, _ := os.Hostname()

			siteNames, ok := message["site_names"].([]interface{})
			if !ok {
				fmt.Println("Invalid message format: 'site_names' is not a list")
				continue
			}

			for _, siteName := range siteNames {
				isAvailableSite := checkWebsite(siteName.(string))
				if !isAvailableSite {
					response := map[string]interface{}{
						"kind":      "autosite",
						"desk_name": deskName,
						"more_text": fmt.Sprintf("%s <b>↓↓↓</b>\n", siteName),
					}
					sendData(response)
				}
			}

			var moreText string
			for _, siteName := range siteNames {
				isAvailableSite := checkWebsite(siteName.(string))
				if isAvailableSite {
					moreText += fmt.Sprintf("%s <b>↑↑↑</b>\n", siteName)
				} else {
					moreText += fmt.Sprintf("%s <b>↓↓↓</b>\n", siteName)
				}
			}

		case "sites":
			fmt.Println("SITES")
			deskName, _ := os.Hostname()

			siteNames, ok := message["site_names"].([]interface{})
			if !ok {
				fmt.Println("Invalid message format: 'site_names' is not a list")
				continue
			}

			var moreText string
			for _, siteName := range siteNames {
				isAvailableSite := checkWebsite(siteName.(string))
				if isAvailableSite {
					moreText += fmt.Sprintf("%s <b>↑↑↑</b>\n", siteName)
				} else {
					moreText += fmt.Sprintf("%s <b>↓↓↓</b>\n", siteName)
				}
			}

			response := map[string]interface{}{
				"kind":            "sites",
				"desk_name":       deskName,
				"more_text":       moreText,
				"message_chat_id": message["message_chat_id"],
			}
			sendData(response)
		default:
			fmt.Println("Unknown message kind:", kind)
		}
	}
}
