package main

import (
	"fmt"
	"log"
	"net"
	"net/http"
	"os"
	"strconv"
	"time"

	"github.com/gorilla/websocket"
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

	// Initialize WebSocket connection
	conn, _, err := websocket.DefaultDialer.Dial(fmt.Sprintf("ws://%s:%s", ip, port), nil)
	if err != nil {
		fmt.Println("Failed to connect to websocket:", err)
		os.Exit(1)
	}
	defer conn.Close()

	handleq(conn)

	// Start WebSocket communication
	handleWebSocket(conn)
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

	// Create SpeedMeasurement object
	speedMeasurement := SpeedMeasurement{
		SendTime:          sendTime.Format("2006-01-02 15:04:05.999"),
		ReceiveTime:       receiveTime.Format("2006-01-02 15:04:05.999"),
		TravelTime:        travelTime,
		TransmissionSpeed: transmissionSpeed,
		Route:             addr.String(),
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
			fmt.Println("Error receiving data from WebSocket:", err)
		}
		return data, err
	}

	// Function to check website availability
	checkWebsite := func(siteName string) bool {
		// Send HTTP GET request to the website
		resp, err := http.Get("http://" + siteName)
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
		case "sites":
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
					moreText += fmt.Sprintf("    - %s FUNCIONANDO\n", siteName)
				} else {
					moreText += fmt.Sprintf("    - %s ERROR\n", siteName)
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
